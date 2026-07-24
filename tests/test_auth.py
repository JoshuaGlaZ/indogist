import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models import User


# ==========================================
# TIER 1: FEATURE COVERAGE (HAPPY PATHS)
# ==========================================

def test_register_page_get(client: TestClient):
    """Tier 1: Accessing registration page returns 200 OK."""
    response = client.get("/accounts/register")
    assert response.status_code == 200
    assert "register" in response.text.lower() or "daftar" in response.text.lower()


def test_login_page_get(client: TestClient):
    """Tier 1: Accessing login page returns 200 OK."""
    response = client.get("/accounts/login")
    assert response.status_code == 200
    assert "login" in response.text.lower() or "masuk" in response.text.lower()


def test_register_post_happy_path(client: TestClient, db_session: Session):
    """Tier 1: User registration with valid data creates user in DB and logs in."""
    register_data = {
        "username": "newuser123",
        "email": "newuser123@example.com",
        "password1": "SecurePass123!",
        "password2": "SecurePass123!"
    }
    response = client.post("/accounts/register", data=register_data, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/"

    # Verify database persistence
    user = db_session.query(User).filter(User.username == "newuser123").first()
    assert user is not None
    assert user.email == "newuser123@example.com"


def test_login_post_happy_path(client: TestClient, test_user: User):
    """Tier 1: User login with correct credentials redirects to home."""
    login_data = {
        "username": test_user.username,
        "password": "password123"
    }
    response = client.post("/accounts/login", data=login_data, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/"


def test_logout(auth_client: TestClient):
    """Tier 1: Logout clears user session and redirects to login."""
    response = auth_client.get("/accounts/logout", follow_redirects=False)
    assert response.status_code == 302
    assert "/accounts/login" in response.headers["location"]


def test_profile_get_authenticated(auth_client: TestClient, test_user: User):
    """Tier 1: Authenticated user can view profile page."""
    response = auth_client.get("/accounts/profile")
    assert response.status_code == 200
    assert test_user.username in response.text


# ==========================================
# TIER 2: BOUNDARY & CORNER CASES
# ==========================================

def test_register_password_mismatch(client: TestClient):
    """Tier 2: Registration rejects mismatched passwords with a flash error."""
    register_data = {
        "username": "mismatchuser",
        "email": "mismatch@example.com",
        "password1": "Password123",
        "password2": "DifferentPassword456"
    }
    response = client.post("/accounts/register", data=register_data)
    assert response.status_code == 200
    assert "Passwords do not match" in response.text or "tidak cocok" in response.text.lower()


def test_register_duplicate_username(client: TestClient, test_user: User):
    """Tier 2: Registration rejects duplicate username."""
    register_data = {
        "username": test_user.username,
        "email": "unique_email@example.com",
        "password1": "Password123",
        "password2": "Password123"
    }
    response = client.post("/accounts/register", data=register_data)
    assert response.status_code == 200
    assert "already taken" in response.text.lower() or "sudah digunakan" in response.text.lower()


def test_register_duplicate_email(client: TestClient, test_user: User):
    """Tier 2: Registration rejects duplicate email address."""
    register_data = {
        "username": "another_unique_name",
        "email": test_user.email,
        "password1": "Password123",
        "password2": "Password123"
    }
    response = client.post("/accounts/register", data=register_data)
    assert response.status_code == 200
    assert "already registered" in response.text.lower() or "sudah terdaftar" in response.text.lower()


def test_login_invalid_credentials(client: TestClient, test_user: User):
    """Tier 2: Login rejects invalid password."""
    login_data = {
        "username": test_user.username,
        "password": "WrongPassword!"
    }
    response = client.post("/accounts/login", data=login_data)
    assert response.status_code == 200
    assert "Invalid username or password" in response.text or "salah" in response.text.lower()


def test_profile_unauthenticated_redirect(client: TestClient):
    """Tier 2: Unauthenticated access to profile redirects to login."""
    response = client.get("/accounts/profile", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "/accounts/login" in response.headers["location"]


def test_profile_email_collision(client: TestClient, db_session: Session, test_user: User):
    """Tier 2: Profile update prevents updating to an email owned by another user."""
    # Create second user
    second_user = User(
        username="seconduser",
        email="second@example.com",
        hashed_password="hashedpassword"
    )
    db_session.add(second_user)
    db_session.commit()

    # Login as test_user
    client.post("/accounts/login", data={"username": test_user.username, "password": "password123"})
    
    # Try updating email to second_user's email
    profile_data = {
        "username": test_user.username,
        "email": "second@example.com"
    }
    response = client.post("/accounts/profile", data=profile_data)
    assert response.status_code == 200
    assert "already in use" in response.text.lower() or "sudah digunakan" in response.text.lower()


# ==========================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# ==========================================

def test_auth_full_lifecycle(client: TestClient, db_session: Session):
    """Tier 3: Register -> Login -> Profile Update -> Logout -> Login again."""
    username = "lifecycleuser"
    email = "lifecycle@example.com"
    password = "LifecyclePass123!"

    # 1. Register
    reg_resp = client.post("/accounts/register", data={
        "username": username, "email": email, "password1": password, "password2": password
    }, follow_redirects=True)
    assert reg_resp.status_code == 200

    # 2. Update Profile
    new_username = "updated_lifecycle"
    prof_resp = client.post("/accounts/profile", data={
        "username": new_username, "email": email
    }, follow_redirects=True)
    assert prof_resp.status_code == 200
    assert new_username in prof_resp.text

    # 3. Logout
    logout_resp = client.get("/accounts/logout", follow_redirects=True)
    assert logout_resp.status_code == 200

    # 4. Login with updated credentials
    login_resp = client.post("/accounts/login", data={
        "username": new_username, "password": password
    }, follow_redirects=True)
    assert login_resp.status_code == 200


# ==========================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS
# ==========================================

def test_auth_special_characters(client: TestClient, db_session: Session):
    """Tier 4: Handles special unicode characters, quotes, and spaces in username/password safely."""
    username = "user_ñáéíóú_#1"
    email = "special_chars@example.com"
    password = "Pässwørd!'\"<script>alert(1)</script>"

    reg_resp = client.post("/accounts/register", data={
        "username": username, "email": email, "password1": password, "password2": password
    }, follow_redirects=False)
    assert reg_resp.status_code == 302

    # Verify user exists in DB
    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None
    assert user.username == username
