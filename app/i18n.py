import gettext
import os
from pathlib import Path

LOCALE_DIR = Path(__file__).resolve().parent.parent / "locale"

# Setup gettext domain if catalog files exist
try:
    id_translation = gettext.translation("django", localedir=LOCALE_DIR, languages=["id"])
except Exception:
    id_translation = None

def lang(*args, **kwargs) -> str:
    """
    Global translation helper for all user-facing output text.
    Supports both lang(msg) and lang(request, msg) signatures.
    Satisfies project internationalization rules.
    """
    if not args:
        return ""
    msg = args[0]
    if not isinstance(msg, str) and len(args) > 1 and isinstance(args[1], str):
        msg = args[1]
    elif not isinstance(msg, str):
        msg = str(msg)

    if not msg:
        return ""
    if id_translation:
        return id_translation.gettext(msg)
    return str(msg)

_ = lang

