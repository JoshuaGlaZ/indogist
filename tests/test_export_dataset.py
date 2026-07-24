import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models import Summary, User
from app.auth import hash_password


# ==========================================
# TIER 1: FEATURE COVERAGE (HAPPY PATHS)
# ==========================================

def test_download_template_get(client: TestClient):
    """Tier 1: Downloading template file returns 200 OK text attachment with template structure."""
    response = client.get("/download-template")
    assert response.status_code == 200
    assert "attachment" in response.headers.get("content-disposition", "")
    assert "TITLE=" in response.text
    assert "TEXT=" in response.text


def test_export_summary_get(auth_client: TestClient, sample_summary: Summary):
    """Tier 1: Exporting summary downloads text file attachment containing title and text."""
    response = auth_client.get(f"/export/{sample_summary.id}")
    assert response.status_code == 200
    assert "attachment" in response.headers.get("content-disposition", "")
    assert sample_summary.title in response.text
    assert sample_summary.summary_text in response.text


def test_add_to_dataset_post(auth_client: TestClient, db_session: Session, sample_summary: Summary):
    """Tier 1: Adding summary to Indosum dataset returns JSON success and updates DB flag."""
    payload = {"summary_id": sample_summary.id}
    response = auth_client.post("/add-to-dataset/", data=payload)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True

    # Verify DB flag updated
    db_session.refresh(sample_summary)
    assert sample_summary.added_to_dataset is True


# ==========================================
# TIER 2: BOUNDARY & CORNER CASES
# ==========================================

def test_export_summary_not_found(client: TestClient):
    """Tier 2: Exporting non-existent summary ID returns 404 status."""
    response = client.get("/export/999999")
    assert response.status_code == 404


def test_add_to_dataset_not_found(client: TestClient):
    """Tier 2: Adding non-existent summary ID to dataset returns 404 error response."""
    response = client.post("/add-to-dataset/", data={"summary_id": 999999})
    assert response.status_code == 404


def test_export_summary_unauthorized(client: TestClient, db_session: Session, sample_summary: Summary):
    """Tier 2: User B cannot export summary owned by User A."""
    # Create User B
    user_b = User(
        username="export_user_b",
        email="export_b@example.com",
        hashed_password=hash_password("password123")
    )
    db_session.add(user_b)
    db_session.commit()

    # Login as User B
    client.post("/accounts/login", data={"username": "export_user_b", "password": "password123"})

    response = client.get(f"/export/{sample_summary.id}")
    assert response.status_code == 403


def test_export_summary_guest_unauthorized(client: TestClient, sample_summary: Summary):
    """Tier 2: Unauthenticated guest cannot export summary owned by a user."""
    response = client.get(f"/export/{sample_summary.id}")
    assert response.status_code == 403


def test_add_to_dataset_guest_unauthorized(client: TestClient, sample_summary: Summary):
    """Tier 2: Unauthenticated guest cannot add user summary to dataset."""
    response = client.post("/add-to-dataset/", data={"summary_id": sample_summary.id})
    assert response.status_code == 403


# ==========================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# ==========================================

def test_export_dataset_lifecycle(client: TestClient, db_session: Session):
    """Tier 3: Register -> Login -> Summarize -> Export -> Add to Dataset."""
    username = "exportflowuser"
    email = "exportflow@example.com"
    password = "FlowPass123!"

    # 1. Register & Login
    client.post("/accounts/register", data={
        "username": username, "email": email, "password1": password, "password2": password
    }, follow_redirects=True)

    # 2. Create Summary
    title = "Lifecycle Export Test Summary"
    text = "Pemerintah provinsi membuka program magang kerja bagi lulusan perguruan tinggi. Program ini bertujuan untuk memberikan pengalaman praktis di industri digital."
    client.post("/summarize/", data={"title": title, "original_text": text, "method": "hybrid"})

    # 3. Retrieve Summary from DB
    summary = db_session.query(Summary).filter(Summary.title == title).first()
    assert summary is not None

    # 4. Export Summary
    exp_resp = client.get(f"/export/{summary.id}")
    assert exp_resp.status_code == 200
    assert title in exp_resp.text

    # 5. Add to Dataset
    ds_resp = client.post("/add-to-dataset/", data={"summary_id": summary.id})
    assert ds_resp.status_code == 200
    assert ds_resp.json()["success"] is True

    # 6. Verify DB updated
    db_session.refresh(summary)
    assert summary.added_to_dataset is True


# ==========================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS
# ==========================================

def test_export_summary_special_characters(auth_client: TestClient, db_session: Session, test_user: User):
    """Tier 4: Exporting summary containing newlines, quotes, and special characters maintains text fidelity."""
    special_title = "Judul 'Khusus' & \"Simbol\""
    special_original = "Baris 1: Teks Berita.\nBaris 2: RincianTambahan & Kuotasi.\nBaris 3: Karakter Khusus 100% Sesuai."
    special_summary = "Baris 1: Teks Berita.\nBaris 2: RincianTambahan."

    summary = Summary(
        user_id=test_user.id,
        title=special_title,
        original_text=special_original,
        summary_text=special_summary,
        method="traditional"
    )
    db_session.add(summary)
    db_session.commit()
    db_session.refresh(summary)

    response = auth_client.get(f"/export/{summary.id}")
    assert response.status_code == 200
    assert special_title in response.text
    assert special_summary in response.text
