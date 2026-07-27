import os

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import datetime
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlmodel import Session

from app.config import settings
from app.database import create_db_and_tables, engine
from app.models import User
from app.auth import get_flash_messages
from app.i18n import (
    lang,
    negotiate_locale,
    get_translations,
    cldr_format_date,
    cldr_format_number,
)
from app.routers import accounts, summarizer

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Indogist", version="1.0.0", debug=settings.DEBUG)


class AnonymousUser:
    is_authenticated = False
    username = ""
    email = ""
    id = None


async def locale_middleware(request: Request, call_next):
    locale = negotiate_locale(request)
    request.state.locale = locale
    request.state.translations = get_translations(locale)
    response = await call_next(request)
    response.headers["Content-Language"] = locale
    return response


async def user_and_messages_middleware(request: Request, call_next):
    user_id = request.session.get("user_id") if "session" in request.scope else None
    user_obj = AnonymousUser()
    if user_id:
        with Session(engine) as db_session:
            user = db_session.get(User, user_id)
            if user:
                user_obj = user
            else:
                if "session" in request.scope:
                    request.session.pop("user_id", None)
    request.state.user = user_obj
    request.scope["user"] = user_obj
    response = await call_next(request)
    return response


# Register User & Locale Middleware inside SessionMiddleware
app.add_middleware(BaseHTTPMiddleware, dispatch=locale_middleware)
app.add_middleware(BaseHTTPMiddleware, dispatch=user_and_messages_middleware)

# Register SessionMiddleware (executes first on incoming requests)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="indogist_session",
    max_age=86400 * 7,
)


# Mount static files
static_dir = BASE_DIR / "static"
if not static_dir.exists():
    static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Setup Jinja2 Templates
templates_dir = BASE_DIR / "templates"
if not templates_dir.exists():
    templates_dir.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))


# Custom Jinja2 Globals & Filters
def _url_for(name: str, *args, **kwargs):
    clean_name = name.replace("summarizer:", "").replace("accounts:", "")
    route_map = {
        "home": "/",
        "summarize": "/summarize/",
        "summary_detail": "/summary/",
        "history": "/history/",
        "charts": "/charts/",
        "comparison": "/comparison/",
        "export_summary": "/export/",
        "add_to_dataset": "/add-to-dataset/",
        "download_template": "/download-template",
        "register": "/accounts/register/",
        "login": "/accounts/login/",
        "logout": "/accounts/logout/",
        "profile": "/accounts/profile/",
    }

    base_url = route_map.get(clean_name, f"/{clean_name}")
    if args:
        base_url = base_url.rstrip("/") + "/" + "/".join(str(a) for a in args) + "/"
    return base_url


def _static_url(path: str):
    return f"/static/{path.lstrip('/')}"


def _truncatechars(value: str, length: int) -> str:
    if not value:
        return ""
    s = str(value)
    if len(s) > length:
        return s[: length - 3] + "..."
    return s


def _truncatewords(value: str, count: int) -> str:
    if not value:
        return ""
    words = str(value).split()
    if len(words) > count:
        return " ".join(words[:count]) + "..."
    return str(value)


def _date_filter(value, format_str: str = "medium", locale: Optional[str] = None):
    return cldr_format_date(value, format_str=format_str, locale=locale)


def _number_filter(value, locale: Optional[str] = None):
    return cldr_format_number(value, locale=locale)


def _escapejs(value: str) -> str:
    if not value:
        return ""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace('"', '\\"')
        .replace("\n", "\\n")
    )


# Enable official Jinja2 i18n extension
templates.env.add_extension("jinja2.ext.i18n")

templates.env.globals.update(
    {
        "url": _url_for,
        "static": _static_url,
        "csrf_field": lambda request: "",
        "now": datetime.datetime.now,
        "hasattr": hasattr,
        "getattr": getattr,
        "_": lang,
        "gettext": lang,
        "lang": lang,
    }
)


def _floatformat(value, decimal_places=1):
    try:
        val = float(value)
        if decimal_places == 0:
            return str(int(round(val)))
        return f"{val:.{decimal_places}f}"
    except (ValueError, TypeError):
        return str(value)


def _linebreaksbr(value):
    if not value:
        return ""
    return str(value).replace("\n", "<br>")


templates.env.filters.update(
    {
        "truncatechars": _truncatechars,
        "truncatewords": _truncatewords,
        "date": _date_filter,
        "format_date": _date_filter,
        "format_number": _number_filter,
        "escapejs": _escapejs,
        "floatformat": _floatformat,
        "linebreaksbr": _linebreaksbr,
        "_": lang,
        "gettext": lang,
        "lang": lang,
        "safe": lambda v: v,
        "default": lambda v, default_val="": v if v else default_val,
        "length": lambda v: len(v) if v else 0,
        "lower": lambda v: str(v).lower() if v else "",
        "upper": lambda v: str(v).upper() if v else "",
    }
)


def render_template(
    request: Request, name: str, context: Optional[dict] = None, status_code: int = 200
):
    ctx = context.copy() if context else {}
    ctx["request"] = request
    curr_locale = getattr(request.state, "locale", negotiate_locale(request))
    ctx["current_locale"] = curr_locale
    # Helper to call standard gettext functions bound to current request
    bound_t = lambda msg: lang(request, msg)
    ctx["_"] = bound_t
    ctx["gettext"] = bound_t
    ctx["lang"] = bound_t
    if "user" not in ctx:
        ctx["user"] = getattr(request.state, "user", AnonymousUser())
    if "messages" not in ctx:
        ctx["messages"] = get_flash_messages(request)
    return templates.TemplateResponse(
        request=request, name=name, context=ctx, status_code=status_code
    )


app.state.render_template = render_template


@app.on_event("startup")
def on_startup():
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config(str(BASE_DIR / "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
        command.upgrade(alembic_cfg, "head")
    except Exception:
        create_db_and_tables()


# Include Routers
app.include_router(accounts.router)
app.include_router(summarizer.router)


# Language Switcher Endpoint
@app.get("/language/{locale}")
def switch_language(locale: str, request: Request):
    """Set preferred locale via cookie and redirect back."""
    if locale in ("id", "en"):
        response = RedirectResponse(
            url=request.headers.get("referer", "/"), status_code=302
        )
        response.set_cookie(
            key="preferred_locale", value=locale, max_age=86400 * 365, httponly=True
        )
        return response
    return RedirectResponse(url="/")
