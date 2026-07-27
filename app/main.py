import logging
import os

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.csrf import CSRFMiddleware
from app.database import create_db_and_tables
from app.middlewares import locale_middleware, user_and_messages_middleware
from app.routers import accounts, summarizer
from app.security import SecurityHeadersMiddleware
from app.templating import (
    BASE_DIR,
    render_template,
)
from app.templating import (
    csrf_field as _csrf_field,  # noqa: F401
)
from app.templating import (
    date_filter as _date_filter,  # noqa: F401
)
from app.templating import (
    escapejs as _escapejs,  # noqa: F401
)
from app.templating import (
    floatformat as _floatformat,  # noqa: F401
)
from app.templating import (
    linebreaksbr as _linebreaksbr,  # noqa: F401
)
from app.templating import (
    number_filter as _number_filter,  # noqa: F401
)
from app.templating import (
    static_url as _static_url,  # noqa: F401
)
from app.templating import (
    truncatechars as _truncatechars,  # noqa: F401
)
from app.templating import (
    truncatewords as _truncatewords,  # noqa: F401
)
from app.templating import (
    url_for as _url_for,  # noqa: F401
)

logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG", "True").lower() == "true" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("indogist")

app = FastAPI(title="Indogist", version="1.0.0", debug=settings.DEBUG)

limiter = Limiter(
    key_func=get_remote_address,
    enabled=os.getenv("TESTING", "False").lower() not in ("true", "1"),
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(BaseHTTPMiddleware, dispatch=locale_middleware)
app.add_middleware(BaseHTTPMiddleware, dispatch=user_and_messages_middleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="indogist_session",
    max_age=86400 * 7,
)

static_dir = BASE_DIR / "static"
if not static_dir.exists():
    static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.state.render_template = render_template


@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    try:
        from ml.status import get_model_status

        status = get_model_status()
        singleton = status.get("singleton", {})
        logger.info(
            "ML Subsystem initialized: format=%s, vectorizer_vocab=%s, pipeline_ready=%s",
            singleton.get("model_format"),
            singleton.get("vocab_size"),
            singleton.get("is_ready"),
        )
    except Exception as err:
        logger.warning("Could not query ML model startup status: %s", err)


app.include_router(accounts.router)
app.include_router(summarizer.router)


@app.get("/health")
def health_check():
    return JSONResponse({"status": "healthy", "version": "1.0.0"})


@app.get("/language/{locale}")
def switch_language(locale: str, request: Request):
    if locale in ("id", "en"):
        response = RedirectResponse(url=request.headers.get("referer", "/"), status_code=302)
        response.set_cookie(
            key="preferred_locale", value=locale, max_age=86400 * 365, httponly=True
        )
        return response
    return RedirectResponse(url="/")
