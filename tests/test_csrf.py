import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_get_request_receives_csrf_cookie():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        assert "csrf_token" in client.cookies


@pytest.mark.asyncio
async def test_post_request_without_csrf_token_blocked():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET page first to obtain CSRF cookie
        await client.get("/")
        cookie_val = client.cookies.get("csrf_token")
        assert cookie_val is not None

        # Send POST without header or form token
        res = await client.post(
            "/accounts/login",
            data={"username": "invalid", "password": "wrongpassword"},
            headers={"X-Force-CSRF-Check": "true"},
        )
        assert res.status_code == 403
        assert "Forbidden" in res.text or "Invalid or missing CSRF token" in res.text


@pytest.mark.asyncio
async def test_post_request_with_valid_csrf_token_passes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET page first to obtain CSRF cookie
        await client.get("/")
        cookie_val = client.cookies.get("csrf_token")
        assert cookie_val is not None

        # Send POST with matching X-CSRF-Token header
        res = await client.post(
            "/accounts/login",
            data={"username": "nonexistent_user", "password": "somepassword"},
            headers={"X-CSRF-Token": cookie_val, "X-Force-CSRF-Check": "true"},
        )
        # Should pass CSRF check and proceed to login router (which returns 200 HTML with flash message)
        assert res.status_code == 200
        assert "Invalid username or password" in res.text or "IndoGist" in res.text


@pytest.mark.asyncio
async def test_htmx_ajax_csrf_error_json_format():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/")
        res = await client.post(
            "/accounts/login",
            data={"username": "test", "password": "test"},
            headers={"HX-Request": "true", "X-Force-CSRF-Check": "true"},
        )
        assert res.status_code == 403
        data = res.json()
        assert data.get("detail") == "Invalid or missing CSRF token"
