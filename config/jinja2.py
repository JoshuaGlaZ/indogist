"""
Jinja2 environment configuration for Django.
Provides custom globals and filters to replace DTL template tags.
"""

import datetime

from django.contrib import messages
from django.contrib.staticfiles.storage import staticfiles_storage
from django.templatetags.static import static
from django.urls import reverse
from django.utils import formats, timezone
from django.utils.safestring import mark_safe
from jinja2 import Environment


def environment(**options):
    """Create and configure the Jinja2 environment."""
    env = Environment(
        extensions=["jinja2.ext.i18n"],
        **options,
    )

    # Custom globals
    env.globals.update(
        {
            "static": static,
            "url": _url,
            "csrf_field": _csrf_input,
            "now": datetime.datetime.now,
            "mark_safe": mark_safe,
            "hasattr": hasattr,
            "getattr": getattr,
        }
    )

    # Custom filters
    env.filters.update(
        {
            "truncatechars": _truncatechars,
            "truncatewords": _truncatewords,
            "date": _date_filter,
            "escapejs": _escapejs,
            "yesno": _yesno,
            "floatformat": _floatformat,
            "join": _join,
            "linebreaksbr": _linebreaksbr,
            "default": _default,
            "length": _length,
            "add": _add,
            "lower": _lower,
            "upper": _upper,
            "capfirst": _capfirst,
            "title": _title,
            "striptags": _striptags,
            "safe": lambda value: mark_safe(value),
        }
    )

    # Wire up real gettext translations so {% trans %} / {% blocktrans %}
    # pick up locale catalogs at render time (see django.utils.translation).
    from django.utils import translation

    env.install_gettext_translations(translation, newstyle=False)

    return env


def _url(name, *args, **kwargs):
    """Reverse a named URL, passing extra positional args as URL args."""
    return reverse(name, args=args, kwargs=kwargs)


def _csrf_input(request):
    """Render CSRF token hidden input for forms."""
    from django.middleware.csrf import get_token

    token = get_token(request)
    return mark_safe(
        f'<input type="hidden" name="csrfmiddlewaretoken" value="{token}">'
    )


def _truncatechars(value, length):
    """Truncate string to N characters."""
    if not value:
        return ""
    if len(value) > length:
        return value[: length - 3] + "..."
    return value


def _truncatewords(value, count):
    """Truncate string to N words."""
    if not value:
        return ""
    words = value.split()
    if len(words) > count:
        return " ".join(words[:count]) + "..."
    return value


def _date_filter(value, format_string=None):
    """Format a date using Django's date formatting."""
    if value is None:
        return ""
    if format_string is None:
        format_string = "F d, Y"
    if hasattr(value, "strftime"):
        return formats.date_format(value, format_string)
    return str(value)


def _escapejs(value):
    """Escape string for use in JavaScript."""
    from django.utils.html import escapejs

    return escapejs(value)


def _yesno(value, true_val="yes", false_val="no", none_val="maybe"):
    """Convert boolean/None to yes/no/maybe or custom values."""
    if value is None:
        return none_val
    if value:
        return true_val
    return false_val


def _floatformat(value, decimal_places=-1):
    """Format a float with given decimal places."""
    if value is None:
        return ""
    try:
        value = float(value)
    except (ValueError, TypeError):
        return str(value)

    if decimal_places == -1:
        # Auto-detect
        return formats.number_format(value, use_l10n=False)
    return formats.number_format(value, decimal_places, use_l10n=False)


def _join(value, separator=", "):
    """Join an iterable with a separator."""
    if not value:
        return ""
    return separator.join(str(item) for item in value)


def _linebreaksbr(value):
    """Convert newlines to <br> tags."""
    if not value:
        return ""
    from django.utils.html import linebreaksbr

    return linebreaksbr(value)


def _default(value, default_value=""):
    """Return default value if value is falsy."""
    return value or default_value


def _length(value):
    """Return length of value."""
    if value is None:
        return 0
    return len(value)


def _add(value, amount):
    """Add amount to value."""
    try:
        return value + amount
    except (TypeError, ValueError):
        return value


def _lower(value):
    """Convert string to lowercase."""
    if not value:
        return ""
    return str(value).lower()


def _upper(value):
    """Convert string to uppercase."""
    if not value:
        return ""
    return str(value).upper()


def _capfirst(value):
    """Capitalize the first character."""
    if not value:
        return ""
    return str(value).capitalize()


def _title(value):
    """Convert string to title case."""
    if not value:
        return ""
    return str(value).title()


def _striptags(value):
    """Strip HTML tags from string."""
    if not value:
        return ""
    from django.utils.html import strip_tags

    return strip_tags(value)
