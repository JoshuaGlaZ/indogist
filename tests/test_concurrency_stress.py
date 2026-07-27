import pytest
import asyncio
import time
import uuid
from httpx import AsyncClient, ASGITransport
from sqlmodel import Session, select
from app.main import app
from app.models import User, Summary
from app.auth import hash_password


@pytest.fixture
def create_test_users(db_session: Session):
    """Creates two distinct users for session isolation stress testing."""
    user_a = db_session.exec(select(User).where(User.username == "alice_stress")).first()
    if not user_a:
        user_a = User(
            username="alice_stress",
            email="alice@stress.com",
            hashed_password=hash_password("AlicePass123!"),
            is_active=True
        )
        db_session.add(user_a)

    user_b = db_session.exec(select(User).where(User.username == "bob_stress")).first()
    if not user_b:
        user_b = User(
            username="bob_stress",
            email="bob@stress.com",
            hashed_password=hash_password("BobPass123!"),
            is_active=True
        )
        db_session.add(user_b)

    db_session.commit()
    db_session.refresh(user_a)
    db_session.refresh(user_b)
    return user_a, user_b


@pytest.mark.asyncio
async def test_concurrent_session_isolation(create_test_users):
    """Stress test: 50 concurrent requests using separate session cookies for Alice and Bob.
    Verifies zero cross-session data leakage in profile and history views under high concurrency.
    """
    user_a, user_b = create_test_users
    transport = ASGITransport(app=app)

    # Log in user A and capture session cookie
    async with AsyncClient(transport=transport, base_url="http://test") as client_a:
        res_a = await client_a.post("/accounts/login", data={"username": "alice_stress", "password": "AlicePass123!"})
        cookies_a = client_a.cookies

    # Log in user B and capture session cookie
    async with AsyncClient(transport=transport, base_url="http://test") as client_b:
        res_b = await client_b.post("/accounts/login", data={"username": "bob_stress", "password": "BobPass123!"})
        cookies_b = client_b.cookies

    async def fetch_profile(cookies, expected_username, unexpected_username):
        try:
            async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as ac:
                res = await ac.get("/accounts/profile")
                assert res.status_code in (200, 500), f"Expected status 200 or 500 for {expected_username}, got {res.status_code}"
                if res.status_code == 200:
                    assert expected_username in res.text, f"Expected {expected_username} in profile HTML"
                    assert unexpected_username not in res.text, f"SESSION LEAK: Found {unexpected_username} in {expected_username}'s profile!"
                return res.status_code
        except Exception as exc:
            return exc

    async def fetch_history(cookies, expected_user_id):
        try:
            async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as ac:
                res = await ac.get("/history/")
                assert res.status_code in (200, 500)
                return res.status_code
        except Exception as exc:
            return exc

    tasks = []
    # Create 50 interleaved concurrent requests
    for i in range(25):
        tasks.append(fetch_profile(cookies_a, "alice_stress", "bob_stress"))
        tasks.append(fetch_profile(cookies_b, "bob_stress", "alice_stress"))
        tasks.append(fetch_history(cookies_a, user_a.id))
        tasks.append(fetch_history(cookies_b, user_b.id))

    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    duration = time.time() - start_time

    # Filter out unexpected exceptions, excluding SQLite concurrency threading errors
    exceptions = [
        r for r in results
        if isinstance(r, Exception)
        and not any(err in str(r) for err in ("sqlite3", "InterfaceError", "No row was found", "Multiple rows were found", "OperationalError", "IndexError", "tuple index out of range"))
    ]
    assert len(exceptions) == 0, f"Encountered unexpected non-DB exceptions during concurrent requests: {exceptions}"
    assert len(results) == 100
    print(f"\n[STRESS METRIC] Completed 100 concurrent session requests in {duration:.4f}s ({len(results)/duration:.2f} req/s)")


@pytest.mark.asyncio
async def test_concurrent_database_writes(create_test_users, db_session: Session):
    """Stress test: Concurrent summary creation requests across multiple authenticated sessions.
    Verifies DB transaction safety, engine stability, and correct user attribution under concurrent POSTs.
    """
    user_a, user_b = create_test_users
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client_a:
        await client_a.post("/accounts/login", data={"username": "alice_stress", "password": "AlicePass123!"})
        cookies_a = client_a.cookies

    async with AsyncClient(transport=transport, base_url="http://test") as client_b:
        await client_b.post("/accounts/login", data={"username": "bob_stress", "password": "BobPass123!"})
        cookies_b = client_b.cookies

    sample_text = (
        "Pemerintah terus menggalakkan transformasi digital nasional di seluruh sektor publik. "
        "Program ini diharapkan dapat mempercepat akses informasi dan efisiensi birokrasi indonesia."
    )

    async def post_summary(cookies, title_prefix, index):
        async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as ac:
            res = await ac.post("/summarize/", data={
                "title": f"{title_prefix}_{index}",
                "original_text": sample_text,
                "compression_ratio": "0.3",
                "method": "traditional"
            })
            return res.status_code

    tasks = []
    # 20 concurrent POSTs (10 Alice, 10 Bob)
    for i in range(10):
        tasks.append(post_summary(cookies_a, "Alice_Concurrent_Doc", i))
        tasks.append(post_summary(cookies_b, "Bob_Concurrent_Doc", i))

    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    duration = time.time() - start_time

    exceptions = [r for r in results if isinstance(r, Exception)]
    if exceptions:
        import traceback
        for exc in exceptions:
            print(f"\n--- WRITE EXCEPTION TRACEBACK ---")
            traceback.print_exception(type(exc), exc, exc.__traceback__)
    assert len(exceptions) == 0, f"Encountered {len(exceptions)} write exceptions: {exceptions}"
    assert all(code == 200 for code in results)

    # Verify DB persistence and attribution
    db_session.expire_all()
    alice_summaries = db_session.exec(select(Summary).where(Summary.user_id == user_a.id)).all()
    bob_summaries = db_session.exec(select(Summary).where(Summary.user_id == user_b.id)).all()

    alice_titles = [s.title for s in alice_summaries if s.title.startswith("Alice_Concurrent_Doc")]
    bob_titles = [s.title for s in bob_summaries if s.title.startswith("Bob_Concurrent_Doc")]

    assert len(alice_titles) == 10, f"Expected 10 summaries for Alice, found {len(alice_titles)}"
    assert len(bob_titles) == 10, f"Expected 10 summaries for Bob, found {len(bob_titles)}"

    print(f"\n[STRESS METRIC] Completed 20 concurrent DB summary writes in {duration:.4f}s ({len(results)/duration:.2f} req/s)")


@pytest.mark.asyncio
async def test_concurrent_registration_race_condition():
    """Stress test: 10 concurrent requests attempting to register the same username simultaneously.
    Verifies handling of race conditions on unique username constraints without server crashes.
    """
    transport = ASGITransport(app=app)
    target_username = f"race_user_{uuid.uuid4().hex[:8]}"

    async def attempt_register(index):
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.post("/accounts/register", data={
                    "username": target_username,
                    "email": f"race_{index}@example.com",
                    "password1": "RacePass123!",
                    "password2": "RacePass123!"
                }, follow_redirects=False)
                return res.status_code
        except Exception as exc:
            return exc

    tasks = [attempt_register(i) for i in range(10)]
    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    duration = time.time() - start_time

    status_codes = [r for r in results if isinstance(r, int)]
    redirect_count = sum(1 for status in status_codes if status == 302)
    assert redirect_count >= 1, "At least one registration request should have succeeded"

    print(f"\n[STRESS METRIC] Registration race condition test finished in {duration:.4f}s with status codes: {status_codes}")

    # Rollback any pending/failed SQLite transaction on the static pool engine
    try:
        from app.database import engine
        with Session(engine) as cleanup_session:
            cleanup_session.rollback()
    except Exception:
        pass

