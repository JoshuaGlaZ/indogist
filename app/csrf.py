import os
import secrets

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse, JSONResponse
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
        testing = os.getenv("TESTING", "False").lower() in ("true", "1")
        force_csrf = request.headers.get("X-Force-CSRF-Check", "").lower() == "true"
        if testing and not force_csrf:
            response = await call_next(request)
            self._ensure_csrf_cookie(request, response)
            return response

        if request.method not in self.EXEMPT_METHODS and not any(
            request.url.path.startswith(p) for p in self.EXEMPT_PATHS
        ):
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
                        header_token = str(
                            form.get("csrf_token")
                            or form.get("_csrf_header")
                            or form.get("csrf")
                            or ""
                        )
                    except Exception:
                        header_token = ""

            if (
                not cookie_token
                or not header_token
                or not validate_csrf_token(cookie_token, header_token)
            ):
                is_ajax = request.headers.get(
                    "HX-Request"
                ) == "true" or "application/json" in request.headers.get("Accept", "")
                if is_ajax:
                    return JSONResponse(
                        {"detail": "Invalid or missing CSRF token"}, status_code=403
                    )
                return HTMLResponse(
                    "<h1>403 Forbidden</h1><p>Invalid or missing CSRF token.</p>", status_code=403
                )

        response = await call_next(request)
        self._ensure_csrf_cookie(request, response)
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
