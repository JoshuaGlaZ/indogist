import os

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

_serializer = URLSafeTimedSerializer(settings.SECRET_KEY)

CSRF_TOKEN_MAX_AGE = 3600


def generate_csrf_token(session_id: str) -> str:
    return _serializer.dumps(session_id, salt="csrf-token")


def validate_csrf_token(token: str, session_id: str) -> bool:
    try:
        _serializer.loads(token, salt="csrf-token", max_age=CSRF_TOKEN_MAX_AGE)
        return True
    except (BadSignature, SignatureExpired):
        return False


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

        session_id = ""
        if "session" in request.scope:
            session_id = str(request.session.get("user_id", ""))

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

        if not token or not validate_csrf_token(str(token), session_id):
            raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

        return await call_next(request)
