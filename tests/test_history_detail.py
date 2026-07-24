import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models import Summary, User
from app.auth import hash_password


# ==========================================
# TIER 1: FEATURE COVERAGE (HAPPY PATHS)
# ==========================================

def test_history_get_guest(client: TestClient):
    """Tier 1: Guest accessing history page receives empty history state."""
    response = client.get("/history/")
    assert response.status_code == 200


def test_history_get_authenticated(auth_client: TestClient, sample_summary: Summary):
    """Tier 1: Authenticated user views history list containing their summaries."""
    response = auth_client.get("/history/")
    assert response.status_code == 200
    assert sample_summary.title in response.text


def test_summary_detail_get(auth_client: TestClient, sample_summary: Summary):
    """Tier 1: Accessing summary detail view renders summary details and stats."""
    response = auth_client.get(f"/summary/{sample_summary.id}/")
    assert response.status_code == 200
    assert sample_summary.title in response.text
    assert sample_summary.summary_text in response.text
    assert sample_summary.original_text in response.text


# ==========================================
# TIER 2: BOUNDARY & CORNER CASES
# ==========================================

def test_summary_detail_not_found(client: TestClient):
    """Tier 2: Requesting non-existent summary ID returns 404 status."""
    response = client.get("/summary/999999/")
    assert response.status_code == 404


def test_history_search_no_results(auth_client: TestClient, sample_summary: Summary):
    """Tier 2: Searching history with non-matching query returns empty list without error."""
    response = auth_client.get("/history/?q=nonexistent_query_term_xyz_123")
    assert response.status_code == 200
    assert sample_summary.title not in response.text or "No summary history" in response.text or "Belum ada" in response.text


def test_history_invalid_sort(auth_client: TestClient, sample_summary: Summary):
    """Tier 2: Providing invalid sort parameter defaults safely to descending creation date."""
    response = auth_client.get("/history/?sort=invalid_column_name")
    assert response.status_code == 200
    assert sample_summary.title in response.text


def test_summary_detail_unauthorized_user(client: TestClient, db_session: Session, sample_summary: Summary):
    """Tier 2: User B cannot access summary detail owned by User A."""
    # Create User B
    user_b = User(
        username="user_b_other",
        email="user_b@example.com",
        hashed_password=hash_password("password123")
    )
    db_session.add(user_b)
    db_session.commit()

    # Login as User B
    client.post("/accounts/login", data={"username": "user_b_other", "password": "password123"})

    # Attempt to view sample_summary (owned by test_user)
    response = client.get(f"/summary/{sample_summary.id}/")
    assert response.status_code == 403


def test_summary_detail_guest_unauthorized(client: TestClient, sample_summary: Summary):
    """Tier 2: Unauthenticated guest cannot access summary detail owned by a user."""
    response = client.get(f"/summary/{sample_summary.id}/")
    assert response.status_code == 403


# ==========================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# ==========================================

def test_history_detail_full_flow(client: TestClient, db_session: Session):
    """Tier 3: Register -> Login -> Create Summary -> View History -> Search -> Detail View."""
    username = "historyflowuser"
    email = "historyflow@example.com"
    password = "FlowPassword123!"

    # 1. Register & Login
    client.post("/accounts/register", data={
        "username": username, "email": email, "password1": password, "password2": password
    }, follow_redirects=True)

    # 2. Create Summary
    title = "Unique History Flow Summary Title"
    text = "Pemerintah meningkatkan anggaran pendidikan nasional sebesar 15 persen untuk tahun depan. Peningkatan ini ditujukan untuk membangun sarana sekolah di daerah 3T."
    client.post("/summarize/", data={"title": title, "original_text": text, "method": "hybrid"})

    # 3. View History
    hist_resp = client.get("/history/")
    assert hist_resp.status_code == 200
    assert title in hist_resp.text

    # 4. Search in History
    search_resp = client.get(f"/history/?q={title}")
    assert search_resp.status_code == 200
    assert title in search_resp.text

    # 5. Open Detail View
    summary_obj = db_session.query(Summary).filter(Summary.title == title).first()
    assert summary_obj is not None

    detail_resp = client.get(f"/summary/{summary_obj.id}/")
    assert detail_resp.status_code == 200
    assert title in detail_resp.text


# ==========================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS
# ==========================================

def test_summary_detail_empty_entities(auth_client: TestClient, db_session: Session, test_user: User):
    """Tier 4: Handles summary detail view gracefully when entities_json is empty or invalid JSON."""
    summary_no_entities = Summary(
        user_id=test_user.id,
        title="Summary Without Entities",
        original_text="Teks asli tanpa entitas.",
        summary_text="Ringkasan tanpa entitas.",
        method="hybrid",
        entities_json="invalid_json_string_test"
    )
    db_session.add(summary_no_entities)
    db_session.commit()
    db_session.refresh(summary_no_entities)

    response = auth_client.get(f"/summary/{summary_no_entities.id}/")
    assert response.status_code == 200
    assert summary_no_entities.title in response.text
