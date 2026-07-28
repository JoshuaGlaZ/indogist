import os
import threading
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

os.environ["TESTING"] = "True"
if not os.environ.get("SECRET_KEY"):
    os.environ["SECRET_KEY"] = "test-secret-key-123456789-for-testing"


import app.database as app_db
import app.main as app_main
from app.auth import hash_password
from app.database import get_session
from app.main import app
from app.models import Summary, User

db_lock = threading.Lock()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Sets up an in-memory SQLite database for the entire test session."""
    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(test_engine)
    app_db.engine = test_engine
    app_main.engine = test_engine

    def override_get_session():
        with db_lock, Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    yield test_engine
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture(name="db_session")
def db_session_fixture(setup_test_database):
    """Provides a fresh transactional database session for direct model queries in tests."""
    engine = setup_test_database
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture():
    """FastAPI TestClient fixture for making unauthenticated HTTP requests."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(name="test_user")
def test_user_fixture(db_session: Session):
    """Creates and returns a standard test user in the database."""
    user = db_session.query(User).filter(User.username == "testuser").first()
    if not user:
        user = User(
            username="testuser",
            email="testuser@example.com",
            hashed_password=hash_password("password123"),
            is_active=True,
            created_at=datetime.now(UTC),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture(name="auth_client")
def auth_client_fixture(client: TestClient, test_user: User):
    """Returns a TestClient logged in with valid session cookies for test_user."""
    response = client.post(
        "/accounts/login",
        data={"username": test_user.username, "password": "password123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    return client


@pytest.fixture(name="sample_summary")
def sample_summary_fixture(db_session: Session, test_user: User):
    """Creates a sample Summary record linked to test_user in the database."""
    original_text = (
        "Pemerintah Indonesia secara resmi mengumumkan kebijakan baru terkait transformasi digital "
        "di sektor pelayanan publik. Kebijakan ini bertujuan untuk meningkatkan efisiensi dan transparansi "
        "layanan kepada masyarakat di seluruh provinsi. Presiden menekankan pentingnya integrasi sistem "
        "antar kementerian dan lembaga pemerintah."
    )
    summary_text = "Pemerintah Indonesia mengumumkan kebijakan transformasi digital pelayanan publik untuk meningkatkan efisiensi."

    summary = Summary(
        user_id=test_user.id,
        title="Transformasi Digital Pelayanan Publik",
        original_text=original_text,
        summary_text=summary_text,
        compression_ratio=0.3,
        method="hybrid",
        created_at=datetime.now(UTC),
        word_count_original=len(original_text.split()),
        word_count_summary=len(summary_text.split()),
        entities_json='[{"text": "Pemerintah Indonesia", "label": "ORGANIZATION", "confidence": 0.95}]',
    )
    db_session.add(summary)
    db_session.commit()
    db_session.refresh(summary)
    return summary
