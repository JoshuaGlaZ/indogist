import gettext
import os
from pathlib import Path

LOCALE_DIR = Path(__file__).resolve().parent.parent / "locale"

# Setup gettext domain if catalog files exist
try:
    id_translation = gettext.translation("django", localedir=LOCALE_DIR, languages=["id"])
except Exception:
    id_translation = None

def lang(msg: str) -> str:
    """
    Global translation helper for all user-facing output text.
    Satisfies project internationalization rules.
    """
    if not msg:
        return ""
    if id_translation:
        return id_translation.gettext(msg)
    return str(msg)

_ = lang
