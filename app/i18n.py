"""
IndoGist Internationalization (i18n) & Localization (l10n) Engine.

Provides CLDR-compliant locale negotiation, Gettext translation catalog management,
universal translation helpers (lang / _), and locale-aware date/number formatting.
"""

from datetime import date, datetime
from functools import lru_cache
import gettext
from pathlib import Path
from typing import Any, List, Optional, Union

from babel import Locale
from babel.dates import (
    format_date as babel_format_date,
    format_datetime as babel_format_datetime,
)
from babel.numbers import format_decimal as babel_format_decimal
from fastapi import Request

# Application Locale Constants
LOCALE_DIR: Path = Path(__file__).resolve().parent.parent / "locale"
SUPPORTED_LOCALES: List[str] = ["id", "en"]
DEFAULT_LOCALE: str = "id"


@lru_cache(maxsize=16)
def _load_translation_catalog(locale: str) -> Optional[gettext.GNUTranslations]:
    """Internal LRU-cached loader for GNU gettext compiled binary catalogs (.mo)."""
    try:
        catalog = gettext.translation("messages", localedir=LOCALE_DIR, languages=[locale])
        if isinstance(catalog, gettext.GNUTranslations):
            return catalog
    except Exception:
        pass
    return None


def get_translations(locale: str) -> Union[gettext.GNUTranslations, gettext.NullTranslations]:
    """Retrieve the gettext translation catalog for the specified locale code.
    
    Returns a GNUTranslations catalog if compiled .mo exists, otherwise a NullTranslations fallback.
    """
    catalog = _load_translation_catalog(locale)
    if catalog is not None:
        return catalog
    return gettext.NullTranslations()


def clear_translation_cache() -> None:
    """Clear the in-memory translation catalog LRU cache (useful during dev/testing)."""
    _load_translation_catalog.cache_clear()


def parse_accept_language(header: str) -> List[str]:
    """Parse HTTP Accept-Language header string into a prioritized list of language codes.
    
    Example: 'en-US,en;q=0.9,id;q=0.8' -> ['en_US', 'en', 'id']
    """
    if not header:
        return []
    languages: List[str] = []
    for item in header.split(","):
        parts = item.strip().split(";")
        lang_code = parts[0].strip().replace("-", "_")
        if lang_code:
            languages.append(lang_code)
            # Also extract 2-letter ISO base code (e.g. 'en_US' -> 'en')
            if "_" in lang_code:
                base_code = lang_code.split("_")[0]
                if base_code not in languages:
                    languages.append(base_code)
    return languages


def negotiate_locale(request: Optional[Request] = None) -> str:
    """Determine the active request locale code using a 4-tier fallback hierarchy:
    
    1. URL Query Parameter: ?lang=id or ?lang=en
    2. Cookie Preference: preferred_locale=id
    3. HTTP Accept-Language Header matching via Babel
    4. Default System Locale ('id')
    """
    if not request:
        return DEFAULT_LOCALE

    # 1. Query parameter override
    query_lang = request.query_params.get("lang")
    if query_lang and query_lang in SUPPORTED_LOCALES:
        return query_lang

    # 2. Cookie preference override
    cookie_lang = request.cookies.get("preferred_locale")
    if cookie_lang and cookie_lang in SUPPORTED_LOCALES:
        return cookie_lang

    # 3. Accept-Language HTTP header negotiation via Babel
    accept_header = request.headers.get("accept-language", "")
    requested = parse_accept_language(accept_header)
    matched = Locale.negotiate(requested, SUPPORTED_LOCALES)
    if matched and matched.language in SUPPORTED_LOCALES:
        return matched.language

    # 4. Default locale fallback
    return DEFAULT_LOCALE


def lang(*args: Any, **kwargs: Any) -> str:
    """Universal Gettext translation helper function.
    
    Supports flexible invocation patterns:
      - lang("Text to translate")
      - lang(request, "Text to translate")
    
    Dynamically resolves locale from request state or negotiation fallback.
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
    catalog = get_translations(target_locale)
    return catalog.gettext(msg)


# Standard Gettext Shorthand Alias
_ = lang


def cldr_format_date(
    value: Union[datetime, date, str, None],
    format_str: str = "medium",
    locale: Optional[str] = None,
) -> str:
    """Format dates and datetimes according to Unicode CLDR standards via Babel."""
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
    value: Union[int, float, str, None],
    locale: Optional[str] = None,
) -> str:
    """Format decimal numbers with locale-appropriate thousand/decimal separators via Babel."""
    if value is None or value == "":
        return ""
    target_locale = locale or DEFAULT_LOCALE
    try:
        return babel_format_decimal(float(value), locale=target_locale)
    except Exception:
        return str(value)
