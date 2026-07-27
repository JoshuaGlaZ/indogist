import datetime
import hashlib
from pathlib import Path
from typing import Optional
from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.csrf import generate_csrf_token
from app.auth import get_flash_messages
from app.i18n import (
    lang,
    negotiate_locale,
    cldr_format_date,
    cldr_format_number,
)
from app.middlewares import AnonymousUser

BASE_DIR = Path(__file__).resolve().parent.parent


def compute_static_hashes() -> dict[str, str]:
    hashes = {}
    static = BASE_DIR / "static"
    if not static.exists():
        return hashes
    for file in static.rglob("*"):
        if file.is_file():
            rel = file.relative_to(static).as_posix()
            try:
                hashes[rel] = hashlib.sha256(file.read_bytes()).hexdigest()[:12]
            except OSError:
                pass
    return hashes


static_hashes = compute_static_hashes()


def url_for(name: str, *args, **kwargs) -> str:
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


def static_url(path: str) -> str:
    clean = path.lstrip("/")
    h = static_hashes.get(clean)
    return f"/static/{clean}?v={h}" if h else f"/static/{clean}"


def truncatechars(value: str, length: int) -> str:
    if not value:
        return ""
    s = str(value)
    if len(s) > length:
        return s[: length - 3] + "..."
    return s


def truncatewords(value: str, count: int) -> str:
    if not value:
        return ""
    words = str(value).split()
    if len(words) > count:
        return " ".join(words[:count]) + "..."
    return str(value)


def date_filter(value, format_str: str = "medium", locale: Optional[str] = None):
    return cldr_format_date(value, format_str=format_str, locale=locale)


def number_filter(value, locale: Optional[str] = None):
    return cldr_format_number(value, locale=locale)


def escapejs(value: str) -> str:
    if not value:
        return ""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace('"', '\\"')
        .replace("\n", "\\n")
    )


def csrf_field(request: Request) -> str:
    session_id = ""
    if "session" in request.scope:
        session_id = str(request.session.get("user_id", ""))
    token = generate_csrf_token(session_id)
    return (
        f'<meta name="csrf-token" content="{token}">'
        f'<script>window.__CSRF_TOKEN="{token}"</script>'
    )


def floatformat(value, decimal_places=1):
    try:
        val = float(value)
        if decimal_places == 0:
            return str(int(round(val)))
        return f"{val:.{decimal_places}f}"
    except (ValueError, TypeError):
        return str(value)


def linebreaksbr(value):
    if not value:
        return ""
    return str(value).replace("\n", "<br>")


templates_dir = BASE_DIR / "templates"
if not templates_dir.exists():
    templates_dir.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

templates.env.add_extension("jinja2.ext.i18n")

templates.env.globals.update(
    {
        "url": url_for,
        "static": static_url,
        "csrf_field": csrf_field,
        "now": datetime.datetime.now,
        "hasattr": hasattr,
        "getattr": getattr,
        "_": lang,
        "gettext": lang,
        "lang": lang,
    }
)

templates.env.filters.update(
    {
        "truncatechars": truncatechars,
        "truncatewords": truncatewords,
        "date": date_filter,
        "format_date": date_filter,
        "format_number": number_filter,
        "escapejs": escapejs,
        "floatformat": floatformat,
        "linebreaksbr": linebreaksbr,
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
    bound_t = lambda msg, *args, **kwargs: lang(request, msg, *args, **kwargs)

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
