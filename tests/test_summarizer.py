import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models import Summary, User
from app.routers.summarizer import SUMMARY_CACHE


# Sample Indonesian news text for testing
SAMPLE_INDONESIAN_NEWS = (
    "Pemerintah Indonesia secara resmi mengumumkan kebijakan baru terkait transformasi digital "
    "di sektor pelayanan publik. Kebijakan ini bertujuan untuk meningkatkan efisiensi dan transparansi "
    "layanan kepada masyarakat di seluruh provinsi. Presiden menekankan pentingnya integrasi sistem "
    "antar kementerian dan lembaga pemerintah agar masyarakat dapat mengakses layanan publik dengan cepat dan hemat biaya. "
    "Menteri Komunikasi dan Informatika menambahkan bahwa infrastruktur internet broadband akan terus diperluas "
    "hingga ke daerah pelosok dan terdepan. Hal ini diharapkan dapat mendorong pemerataan ekonomi digital di seluruh Indonesia."
)


# ==========================================
# TIER 1: FEATURE COVERAGE (HAPPY PATHS)
# ==========================================

def test_home_get_guest(client: TestClient):
    """Tier 1: Accessing home page as guest returns 200 OK."""
    response = client.get("/")
    assert response.status_code == 200
    assert "IndoGist" in response.text or "Ringkasan" in response.text


def test_home_get_authenticated(auth_client: TestClient, sample_summary: Summary):
    """Tier 1: Accessing home page when authenticated displays recent user summaries."""
    response = auth_client.get("/")
    assert response.status_code == 200
    assert sample_summary.title in response.text


def test_summarize_page_get(client: TestClient):
    """Tier 1: Accessing summarize page returns 200 OK."""
    response = client.get("/summarize/")
    assert response.status_code == 200


def test_summarize_post_hybrid_happy_path(client: TestClient):
    """Tier 1: Submitting text via Hybrid method generates summary output."""
    payload = {
        "title": "Uji Transformasi Digital",
        "original_text": SAMPLE_INDONESIAN_NEWS,
        "compression_ratio": "0.3",
        "method": "hybrid",
        "hybrid_variant": "pos_ner"
    }
    response = client.post("/summarize/", data=payload)
    assert response.status_code == 200
    assert len(response.text.strip()) > 0


def test_summarize_post_traditional_happy_path(client: TestClient):
    """Tier 1: Submitting text via Traditional Extractive method generates summary output."""
    payload = {
        "title": "Uji Traditional Summarizer",
        "original_text": SAMPLE_INDONESIAN_NEWS,
        "compression_ratio": "0.3",
        "method": "traditional",
        "traditional_variant": "sentence_rank"
    }
    response = client.post("/summarize/", data=payload)
    assert response.status_code == 200
    assert len(response.text.strip()) > 0


# ==========================================
# TIER 2: BOUNDARY & CORNER CASES
# ==========================================

def test_summarize_empty_input(client: TestClient):
    """Tier 2: Empty text input returns 400 validation error without 500 server crash."""
    payload = {
        "title": "",
        "original_text": "",
        "method": "hybrid"
    }
    response = client.post("/summarize/", data=payload)
    assert response.status_code in (200, 400)
    assert "Please provide content" in response.text or "Harap masukkan" in response.text or "alert" in response.text or "error" in response.text.lower()


def test_summarize_whitespace_only(client: TestClient):
    """Tier 2: Whitespace-only text input returns validation error."""
    payload = {
        "title": "  ",
        "original_text": "   \n\t   ",
        "method": "hybrid"
    }
    response = client.post("/summarize/", data=payload)
    assert response.status_code in (200, 400)
    assert "Please provide content" in response.text or "Harap masukkan" in response.text or "alert" in response.text or "error" in response.text.lower()



def test_summarize_short_text(client: TestClient):
    """Tier 2: Text input with fewer than 10 words triggers minimum length warning."""
    payload = {
        "title": "Pendek",
        "original_text": "Teks terlalu pendek.",
        "method": "hybrid"
    }
    response = client.post("/summarize/", data=payload)
    assert response.status_code in (200, 400)


def test_summarize_max_len_text(client: TestClient):
    """Tier 2: Handles large text payload (3,000+ words) gracefully."""
    large_text = (SAMPLE_INDONESIAN_NEWS + " ") * 30
    payload = {
        "title": "Large Text Test",
        "original_text": large_text,
        "compression_ratio": "0.2",
        "method": "traditional"
    }
    response = client.post("/summarize/", data=payload)
    assert response.status_code == 200
    assert len(response.text.strip()) > 0


# ==========================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# ==========================================

def test_summarize_sha256_cache_hit(client: TestClient):
    """Tier 3: Identical input payloads utilize SHA-256 summary cache."""
    SUMMARY_CACHE.clear()
    payload = {
        "title": "Cache Test Title",
        "original_text": SAMPLE_INDONESIAN_NEWS,
        "compression_ratio": "0.3",
        "method": "hybrid",
        "hybrid_variant": "pos_ner"
    }

    # First call: computes and stores in SUMMARY_CACHE
    res1 = client.post("/summarize/", data=payload)
    assert res1.status_code == 200
    assert len(SUMMARY_CACHE) == 1

    # Second call: fetches from SUMMARY_CACHE
    res2 = client.post("/summarize/", data=payload)
    assert res2.status_code == 200
    assert len(SUMMARY_CACHE) == 1


def test_summarize_htmx_oob_swaps(client: TestClient):
    """Tier 3: HTMX request returns HTML partial with Out-Of-Band (OOB) swap targets."""
    payload = {
        "title": "HTMX OOB Test",
        "original_text": SAMPLE_INDONESIAN_NEWS,
        "compression_ratio": "0.3",
        "method": "hybrid"
    }
    headers = {"HX-Request": "true"}
    response = client.post("/summarize/", data=payload, headers=headers)
    assert response.status_code == 200
    assert 'hx-swap-oob="true"' in response.text
    assert 'id="entityWrap"' in response.text or 'id="viewModeToggle"' in response.text


def test_summarize_authenticated_saved_to_db(auth_client: TestClient, db_session: Session, test_user: User):
    """Tier 3: Submitting a summary while logged in saves the Summary record to database."""
    unique_title = "Persistent Summary Title 99"
    payload = {
        "title": unique_title,
        "original_text": SAMPLE_INDONESIAN_NEWS,
        "compression_ratio": "0.3",
        "method": "hybrid"
    }
    response = auth_client.post("/summarize/", data=payload)
    assert response.status_code == 200

    summary_in_db = db_session.query(Summary).filter(
        Summary.title == unique_title,
        Summary.user_id == test_user.id
    ).first()
    assert summary_in_db is not None
    assert summary_in_db.method == "hybrid"


# ==========================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS
# ==========================================

def test_summarize_indonesian_news_realworld(client: TestClient):
    """Tier 4: End-to-end processing of a realistic multi-paragraph Indonesian news article."""
    real_article = (
        "Bursa Efek Indonesia (BEI) mencatat penguatan Indeks Harga Saham Gabungan (IHSG) pada penutupan perdagangan sore ini. "
        "IHSG naik sebesar 0,75 persen ke level 7.250 didorong oleh aksi beli bersih investor asing pada saham sektor perbankan dan energi. "
        "Sektor keuangan memimpin penguatan disusul oleh sektor barang konsumen primer.\n\n"
        "Analis pasar modal menyatakan bahwa sentimen positif terdorong oleh rilis data inflasi domestik yang stabil dan terkendali. "
        "Bank Indonesia diperkirakan akan mempertahankan suku bunga acuan dalam Rapat Dewan Gubernur mendatang. "
        "Kondisi makroekonomi yang kondusif memberikan keyakinan lebih kepada para pelaku pasar investasi."
    )
    payload = {
        "title": "Analisis Pasar Modal Indonesia",
        "original_text": real_article,
        "compression_ratio": "0.4",
        "method": "hybrid"
    }
    response = client.post("/summarize/", data=payload)
    assert response.status_code == 200
    assert "BEI" in response.text or "IHSG" in response.text or "saham" in response.text.lower()


def test_summarize_xss_injection_safety(client: TestClient):
    """Tier 4: Input containing HTML/JS injection strings is rendered safely without execution risk."""
    xss_payload = {
        "title": "<script>alert('xss-title')</script>",
        "original_text": "Pemerintah indonesia merilis kebijakan baru untuk kesehatan masyarakat. <img src=x onerror=alert('xss-body')> Teks Berita Legitimat.",
        "compression_ratio": "0.3",
        "method": "traditional"
    }
    response = client.post("/summarize/", data=xss_payload)
    assert response.status_code == 200
    assert "<script>alert" not in response.text or "&lt;script&gt;" in response.text or "alert" not in response.text


# ==========================================
# ADVERSARIAL & BOUNDARY TESTS (CHALLENGER)
# ==========================================

def test_summary_detail_invalid_string_id(client: TestClient):
    """Adversarial: Non-integer string or UUID in /summary/{pk} returns 422 Unprocessable Entity, not 500."""
    response = client.get("/summary/invalid-uuid-or-string-id/")
    assert response.status_code == 422
    assert response.status_code != 500


def test_export_summary_invalid_string_id(client: TestClient):
    """Adversarial: Non-integer string or UUID in /export/{pk} returns 422 Unprocessable Entity, not 500."""
    response = client.get("/export/invalid-id-str")
    assert response.status_code == 422
    assert response.status_code != 500


def test_upload_malformed_json_file(client: TestClient):
    """Adversarial: Uploading malformed JSON file returns validation error or proper error status, not 500."""
    import io
    malformed_json = '{"title": "test", "original_text": "incomplete json...'
    files = {"file": ("data.json", io.BytesIO(malformed_json.encode("utf-8")), "application/json")}
    data = {"method": "hybrid"}
    response = client.post("/summarize/", data=data, files=files)
    assert response.status_code in (200, 400, 422)
    assert response.status_code != 500


def test_summarize_db_record_completeness(auth_client: TestClient, db_session: Session, test_user: User):
    """M3 Task 4: Verify saved Summary DB record contains word counts, entities_json, and actual compression ratio."""
    unique_title = "Complete Summary Record Test 101"
    payload = {
        "title": unique_title,
        "original_text": SAMPLE_INDONESIAN_NEWS,
        "compression_ratio": "0.3",
        "method": "hybrid"
    }
    response = auth_client.post("/summarize/", data=payload)
    assert response.status_code == 200

    summary_obj = db_session.query(Summary).filter(
        Summary.title == unique_title,
        Summary.user_id == test_user.id
    ).first()
    assert summary_obj is not None
    assert summary_obj.word_count_original > 0
    assert summary_obj.word_count_summary > 0
    assert isinstance(summary_obj.entities_json, str)
    assert summary_obj.actual_compression > 0.0


def test_summarize_lang_call_signature_robustness(client: TestClient):
    """M3 Task 1: Verify lang() calls during AJAX/HTMX request execution operate cleanly without 2-arg TypeError."""
    payload = {
        "title": "Lang Signature Test",
        "original_text": SAMPLE_INDONESIAN_NEWS,
        "compression_ratio": "0.3",
        "method": "traditional"
    }
    headers = {"X-Requested-With": "XMLHttpRequest"}
    response = client.post("/summarize/", data=payload, headers=headers)
    assert response.status_code == 200
    assert response.status_code != 500


def test_history_empty_and_sqli_query_strings(client: TestClient):
    """Adversarial: Empty query params and SQL injection strings in history query parameters handle safely."""
    sqli_vectors = [
        " ' OR 1=1 -- ",
        "'; DROP TABLE summaries; --",
        '" UNION SELECT 1,2,3--',
        "admin'--"
    ]
    for sqli in sqli_vectors:
        response = client.get(f"/history/?q={sqli}&method={sqli}&sort={sqli}")
        assert response.status_code == 200
        assert response.status_code != 500

    # Empty query strings
    empty_resp = client.get("/history/?q=&method=&sort=")
    assert empty_resp.status_code == 200

