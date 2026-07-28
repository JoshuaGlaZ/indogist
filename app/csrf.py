import os
import secrets

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

CSRF_TOKEN_LENGTH = 32


def generate_csrf_token(request: Request) -> str:
    if "session" not in request.scope:
        return ""
    session = request.session
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(CSRF_TOKEN_LENGTH)
        session["_csrf_token"] = token
    return token


def regenerate_csrf_token(request: Request) -> str:
    """Generate a fresh CSRF token, replacing any existing one.

    Should be called after privilege elevation (login, register) so that
    tokens issued under a pre-auth session cannot be reused after login.
    """
    if "session" not in request.scope:
        return ""
    token = secrets.token_urlsafe(CSRF_TOKEN_LENGTH)
    request.session["_csrf_token"] = token
    return token


def validate_csrf_token(token: str, request: Request) -> bool:
    if "session" not in request.scope:
        return False
    stored = request.session.get("_csrf_token", "")
    return secrets.compare_digest(token or "", stored)


class CSRFMiddleware(BaseHTTPMiddleware):
    EXEMPT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
    EXEMPT_PATHS = frozenset({"/health", "/language/"})

    async def dispatch(self, request: Request, call_next):
        if os.getenv("TESTING", "False").lower() in ("true", "1"):
            return await call_next(request)

        if request.method in self.EXEMPT_METHODS:
            return await call_next(request)

        if any(request.url.path.startswith(p) for p in self.EXEMPT_PATHS):
            return await call_next(request)

        token = request.headers.get("X-CSRF-Token", "")
        if not token:
            content_type = request.headers.get("Content-Type", "")
            if (
                "application/x-www-form-urlencoded" in content_type
                or "multipart/form-data" in content_type
            ):
                try:
                    form = await request.form()
                    token = (
                        form.get("csrf_token") or form.get("_csrf_header") or form.get("csrf") or ""
                    )
                except Exception:
                    token = ""

        if not token or not validate_csrf_token(str(token), request):
            raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

        return await call_next(request)
