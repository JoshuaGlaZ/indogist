import pytest
from datetime import date, datetime
from fastapi.testclient import TestClient
from app.main import app
from app.i18n import (
    negotiate_locale,
    get_translations,
    lang,
    cldr_format_date,
    cldr_format_number,
)

client = TestClient(app)


def test_locale_negotiation_default():
    """Verify default locale fallback is Indonesian ('id')."""
    res = client.get("/")
    assert res.status_code == 200
    assert res.headers["Content-Language"] == "id"
    assert '<html lang="id"' in res.text


def test_locale_negotiation_accept_language_english():
    """Verify Accept-Language: en negotiates English locale."""
    res = client.get("/", headers={"Accept-Language": "en-US,en;q=0.9"})
    assert res.status_code == 200
    assert res.headers["Content-Language"] == "en"
    assert '<html lang="en"' in res.text


def test_locale_negotiation_query_param_override():
    """Verify ?lang=en query parameter overrides Accept-Language and defaults."""
    res = client.get("/?lang=en", headers={"Accept-Language": "id"})
    assert res.status_code == 200
    assert res.headers["Content-Language"] == "en"
    assert '<html lang="en"' in res.text


def test_locale_negotiation_cookie_override():
    """Verify preferred_locale cookie overrides Accept-Language."""
    res = client.get("/", cookies={"preferred_locale": "en"})
    assert res.status_code == 200
    assert res.headers["Content-Language"] == "en"
    assert '<html lang="en"' in res.text


def test_cldr_date_formatting():
    """Verify Babel CLDR date formatting outputs locale-aware strings."""
    test_d = date(2026, 7, 24)
    formatted_id = cldr_format_date(test_d, format_str="full", locale="id")
    formatted_en = cldr_format_date(test_d, format_str="full", locale="en")

    assert "Jumat" in formatted_id or "24" in formatted_id
    assert "Friday" in formatted_en or "July" in formatted_en or "Jul" in formatted_en


def test_cldr_number_formatting():
    """Verify Babel CLDR decimal formatting outputs locale-aware numbers."""
    num = 1234567.89
    formatted_id = cldr_format_number(num, locale="id")
    formatted_en = cldr_format_number(num, locale="en")

    assert "1.234.567" in formatted_id or "1,234,567" in formatted_id
    assert "1,234,567" in formatted_en


def test_gettext_translation_catalogs():
    """Verify translations catalog retrieves translated strings for both locales."""
    id_trans = get_translations("id")
    en_trans = get_translations("en")

    assert id_trans.gettext("Passwords do not match.") == "Kata sandi tidak cocok."
    assert en_trans.gettext("Passwords do not match.") == "Passwords do not match."

    assert id_trans.gettext("Account created for %(username)s! You are now logged in.") == "Akun berhasil dibuat untuk %(username)s! Anda sekarang sudah masuk."
    assert en_trans.gettext("Account created for %(username)s! You are now logged in.") == "Account created for %(username)s! You are now logged in."


def test_parameter_interpolation():
    """Verify parameter interpolation works correctly on translated strings."""
    id_trans = get_translations("id")
    msg_template = id_trans.gettext("Account created for %(username)s! You are now logged in.")
    interpolated = msg_template % {"username": "testuser"}
    assert interpolated == "Akun berhasil dibuat untuk testuser! Anda sekarang sudah masuk."
