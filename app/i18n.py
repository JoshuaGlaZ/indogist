import gettext
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union
from datetime import datetime, date

from babel import Locale
from babel.dates import (
    format_date as babel_format_date,
    format_datetime as babel_format_datetime,
)
from babel.numbers import format_decimal as babel_format_decimal
from fastapi import Request

LOCALE_DIR = Path(__file__).resolve().parent.parent / "locale"
SUPPORTED_LOCALES = ["id", "en"]
DEFAULT_LOCALE = "id"


@lru_cache(maxsize=16)
def get_translations(locale: str) -> gettext.NullTranslations:
    """Load and cache gettext translations catalog for a given locale."""
    try:
        return gettext.translation("messages", localedir=LOCALE_DIR, languages=[locale])
    except Exception:
        return gettext.NullTranslations()


def parse_accept_language(header: str) -> List[str]:
    """Parse HTTP Accept-Language header into ordered list of language codes."""
    if not header:
        return []
    languages = []
    for item in header.split(","):
        parts = item.strip().split(";")
        lang_code = parts[0].strip().replace("-", "_")
        if lang_code:
            languages.append(lang_code)
            # Also append 2-letter base code if full locale (e.g. 'en_US' -> 'en')
            if "_" in lang_code:
                languages.append(lang_code.split("_")[0])
    return languages


def negotiate_locale(request: Optional[Request] = None) -> str:
    """
    Determine request locale with priority:
    1. Query Parameter (?lang=en)
    2. Cookie (preferred_locale=en)
    3. Accept-Language Header matching via Babel
    4. Default Locale fallback ('id')
    """
    if not request:
        return DEFAULT_LOCALE

    # 1. Query param
    query_lang = request.query_params.get("lang")
    if query_lang and query_lang in SUPPORTED_LOCALES:
        return query_lang

    # 2. Cookie
    cookie_lang = request.cookies.get("preferred_locale")
    if cookie_lang and cookie_lang in SUPPORTED_LOCALES:
        return cookie_lang

    # 3. Accept-Language header
    accept_header = request.headers.get("accept-language", "")
    requested = parse_accept_language(accept_header)
    matched = Locale.negotiate(requested, SUPPORTED_LOCALES)
    if matched:
        return matched.language

    return DEFAULT_LOCALE


def lang(*args, **kwargs) -> str:
    """
    Global translation helper. Supports both lang(msg) and lang(request, msg) signatures.
    Resolves locale dynamically based on request or falls back to default locale catalog.
    """
    if not args:
        return ""

    req: Optional[Request] = None
    msg: str = ""

    if isinstance(args[0], Request):
        req = args[0]
        msg = str(args[1]) if len(args) > 1 else ""
    else:
        msg = str(args[0])

    if not msg:
        return ""

    target_locale = (
        req.state.locale
        if (req and hasattr(req.state, "locale"))
        else negotiate_locale(req)
    )
    translation = get_translations(target_locale)
    return translation.gettext(msg)


_ = lang


def cldr_format_date(
    value: Union[datetime, date, str],
    format_str: str = "medium",
    locale: Optional[str] = None,
) -> str:
    """CLDR-compliant date formatting via Babel."""
    if not value:
        return ""
    target_locale = locale or DEFAULT_LOCALE
    try:
        if isinstance(value, datetime):
            return babel_format_datetime(value, format=format_str, locale=target_locale)
        elif isinstance(value, date):
            return babel_format_date(value, format=format_str, locale=target_locale)
        return str(value)
    except Exception:
        return str(value)


def cldr_format_number(
    value: Union[int, float, str], locale: Optional[str] = None
) -> str:
    """CLDR-compliant decimal number formatting via Babel."""
    if value is None:
        return ""
    target_locale = locale or DEFAULT_LOCALE
    try:
        return babel_format_decimal(float(value), locale=target_locale)
    except Exception:
        return str(value)
