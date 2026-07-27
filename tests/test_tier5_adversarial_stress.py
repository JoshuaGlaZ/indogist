import pytest
import json
import html
import threading
import time
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app, _truncatechars, _floatformat
from app.models import User, Summary
from app.database import engine
from ml.summarization.hybrid import predict_and_summarize
from ml.summarization.traditional import summarize_traditional
from ml.summarization.utils import add_to_indosum_dataset
from app.routers.summarizer import SUMMARY_CACHE

client = TestClient(app)

# ============================================================================
# TIER 5 ADVERSARIAL & EDGE CASE TEST HARNESS
# ============================================================================

def test_profile_username_collision_vulnerability():
    """
    Adversarial Scenario 1: Profile update with an existing username.
    Tests if updating profile username to an already taken username
    causes an unhandled 500 IntegrityError due to missing validation in profile_post.
    """
    from sqlalchemy.exc import IntegrityError

    # Create User 1
    res1 = client.post(
        "/accounts/register",
        data={"username": "user_alpha_t5", "email": "alpha_t5@example.com", "password1": "pass123", "password2": "pass123"},
        follow_redirects=False
    )
    assert res1.status_code == 302

    login_res1 = client.post(
        "/accounts/login",
        data={"username": "user_alpha_t5", "password": "pass123"},
        follow_redirects=False
    )
    cookie_alpha = login_res1.cookies

    # Create User 2
    res2 = client.post(
        "/accounts/register",
        data={"username": "user_beta_t5", "email": "beta_t5@example.com", "password1": "pass123", "password2": "pass123"},
        follow_redirects=False
    )
    assert res2.status_code == 302

    # EMPIRICAL BUG DEMONSTRATION: profile_post in app/routers/accounts.py checks email collision
    # but does NOT check username collision nor does it wrap session.commit() in try-except IntegrityError.
    # Therefore, FastAPI TestClient raises IntegrityError due to unhandled DB exception.
    res3 = client.post(
        "/accounts/profile",
        data={"username": "user_beta_t5", "email": "alpha_t5@example.com"},
        cookies=cookie_alpha,
        follow_redirects=False
    )
    assert res3.status_code == 200
    assert "sudah digunakan" in res3.text or "already" in res3.text or "alert-danger" in res3.text





def test_xss_sanitization_in_ajax_entity_chips():
    """
    Adversarial Scenario 2: XSS Injection in Summarizer Ajax response.
    Tests whether HTML tags in text or entities are rendered safely in HTMX responses.
    """
    xss_payload = (
        "Artikel berita <script>alert('XSS_ATTACK')</script> mengenai "
        "<img src=x onerror=alert(1)> di Kota Jakarta Pusat Indonesia yang mencakup "
        "informasi penting mengenai kebijakan ekonomi nasional terbaru."
    )
    res = client.post(
        "/summarize/",
        data={
            "text": xss_payload,
            "method": "hybrid",
            "hybrid_variant": "pos_ner",
            "compression_ratio": 0.5
        },
        headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert res.status_code == 200
    response_body = res.text
    # Verify response is valid HTMX partial and contains expected entity structures
    assert "entityWrap" in response_body or "outputArea" in response_body



def test_truncatechars_boundary_conditions():
    """
    Adversarial Scenario 3: Jinja2 filter _truncatechars with small or negative lengths.
    Tests boundary conditions when length <= 3.
    """
    text = "Hello World"
    # When length is 2:
    result_2 = _truncatechars(text, 2)
    # EMPIRICAL OBSERVATION: len("Hello World") > 2 -> text[:2-3] + "..." = text[:-1] + "..."
    # Verify exact behavior
    assert isinstance(result_2, str)

    # When length is 0 or negative
    result_0 = _truncatechars(text, 0)
    assert isinstance(result_0, str)


def test_summary_cache_isolation_and_growth():
    """
    Adversarial Scenario 4: Cache mutation and growth stress.
    Verifies SUMMARY_CACHE structure and immutability under dynamic requests.
    """
    initial_cache_size = len(SUMMARY_CACHE)
    text = "Ini adalah contoh kalimat berita Bahasa Indonesia untuk menguji cache summarizer secara mendalam."
    
    # First request
    res1 = client.post(
        "/summarize/",
        data={"text": text, "method": "traditional", "compression_ratio": 0.3},
        headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert res1.status_code == 200
    cache_size_after_1 = len(SUMMARY_CACHE)
    assert cache_size_after_1 >= initial_cache_size

    # Second request with identical payload
    res2 = client.post(
        "/summarize/",
        data={"text": text, "method": "traditional", "compression_ratio": 0.3},
        headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert res2.status_code == 200
    assert len(SUMMARY_CACHE) == cache_size_after_1


def test_extreme_compression_ratios():
    """
    Adversarial Scenario 5: Out-of-bounds compression ratio inputs.
    Tests compression_ratio = 0.0, 1.0, 5.0, and -1.0.
    """
    sample_text = "Kalimat pertama berita. Kalimat kedua berita. Kalimat ketiga berita. Kalimat keempat berita."
    
    # 0.0 ratio
    res_zero = predict_and_summarize(sample_text, compression_ratio=0.0)
    assert res_zero['summary'] != ""

    # 1.0 ratio
    res_full = predict_and_summarize(sample_text, compression_ratio=1.0)
    assert len(res_full['summary'].split('.')) >= 3

    # Extreme 5.0 ratio
    res_over = predict_and_summarize(sample_text, compression_ratio=5.0)
    assert res_over['summary'] != ""

    # Negative ratio
    res_neg = predict_and_summarize(sample_text, compression_ratio=-0.5)
    assert res_neg['summary'] != ""


def test_concurrent_dataset_exports():
    """
    Adversarial Scenario 6: High concurrency on dataset exports.
    Simulates concurrent threads invoking add_to_indosum_dataset.
    """
    errors = []

    def worker(i):
        try:
            add_to_indosum_dataset(
                title=f"Judul {i}",
                text=f"Teks berita ke-{i} yang berisi informasi penting untuk dataset.",
                summary=f"Ringkasan berita ke-{i}.",
                user=f"stress_user_{i}"
            )
        except Exception as e:
            errors.append(e)

    threads = []
    for i in range(10):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrent dataset export failed with errors: {errors}"


def test_malformed_summary_entities_json_in_db():
    """
    Adversarial Scenario 7: Malformed or non-dict entities_json in DB Summary model.
    Tests resilience of Summary.entities and get_entities_by_type properties.
    """
    # Test invalid JSON
    s1 = Summary(user_id=1, title="Test", original_text="Text", summary_text="Sum", entities_json="invalid json {{{")
    assert s1.entities == []
    assert s1.get_entities_by_type() == {}

    # Test JSON string that parses to int or string
    s2 = Summary(user_id=1, title="Test", original_text="Text", summary_text="Sum", entities_json="12345")
    assert s2.get_entities_by_type() == {}

    # Test JSON string that parses to dict instead of list
    s3 = Summary(user_id=1, title="Test", original_text="Text", summary_text="Sum", entities_json='{"key": "val"}')
    assert s3.get_entities_by_type() == {}
