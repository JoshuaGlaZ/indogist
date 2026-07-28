import os
import secrets

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

CSRF_TOKEN_COOKIE = "csrf_token"
CSRF_TOKEN_LENGTH = 32


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(CSRF_TOKEN_LENGTH)


def validate_csrf_token(cookie_token: str, header_token: str) -> bool:
    return secrets.compare_digest(cookie_token, header_token)


class CSRFMiddleware(BaseHTTPMiddleware):
    COOKIE_NAME = CSRF_TOKEN_COOKIE
    EXEMPT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
    EXEMPT_PATHS = frozenset({"/health", "/language/"})

    async def dispatch(self, request: Request, call_next):
        if os.getenv("TESTING", "False").lower() in ("true", "1"):
            return await call_next(request)

        response = await call_next(request)
        self._ensure_csrf_cookie(request, response)

        if request.method in self.EXEMPT_METHODS:
            return response

        if any(request.url.path.startswith(p) for p in self.EXEMPT_PATHS):
            return response

        cookie_token = request.cookies.get(self.COOKIE_NAME, "")
        header_token = request.headers.get("X-CSRF-Token", "")

        if not header_token:
            content_type = request.headers.get("Content-Type", "")
            if (
                "application/x-www-form-urlencoded" in content_type
                or "multipart/form-data" in content_type
            ):
                try:
                    form = await request.form()
                    header_token = (
                        form.get("csrf_token") or form.get("_csrf_header") or form.get("csrf") or ""
                    )
                except Exception:
                    header_token = ""

        if not header_token or not validate_csrf_token(cookie_token, header_token):
            raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

        return response

    def _ensure_csrf_cookie(self, request: Request, response: StarletteResponse) -> None:
        if not isinstance(response, StarletteResponse):
            return
        if self.COOKIE_NAME not in request.cookies:
            response.set_cookie(
                self.COOKIE_NAME,
                generate_csrf_token(),
                httponly=False,
                samesite="lax",
                path="/",
            )
