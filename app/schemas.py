from typing import Optional, Tuple
from fastapi import UploadFile
from app.i18n import lang

def parse_uploaded_file_content(content_str: str) -> Tuple[str, str]:
    """Parse uploaded text file with template format (TITLE= and TEXT=)."""
    lines = content_str.split("\n")
    title = ""
    text = ""
    capture_text = False

    for i, line in enumerate(lines):
        if line.strip().startswith("TITLE="):
            title_on_line = line.split("TITLE=", 1)[1].strip()
            if title_on_line:
                title = title_on_line
            else:
                for next_line in lines[i + 1 :]:
                    if next_line.strip() and not next_line.strip().startswith("TEXT="):
                        title = next_line.strip()
                        break
        elif line.strip().startswith("TEXT="):
            text_on_line = line.split("TEXT=", 1)[1].strip()
            if text_on_line:
                text = text_on_line + "\n"
            capture_text = True
            continue
        elif capture_text:
            text += line + "\n"

    text = text.strip()
    if not title or not text:
        raise ValueError(
            lang(
                "File format invalid. Please ensure:\n"
                "1. TITLE= is present with a title\n"
                "2. TEXT= is present with text content\n"
                "Use the official template."
            )
        )
    return title, text

def is_template_format(content_str: str) -> bool:
    return "TITLE=" in content_str and "TEXT=" in content_str

def validate_input_edge_cases(title: str, text: str, has_file: bool, file_content: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    has_title = bool(title and title.strip())
    has_text = bool(text and text.strip())

    if not has_title and not has_text and not has_file:
        return False, lang("Please provide content to summarize. You must either:\n• Enter a title and text manually, OR\n• Upload a file using the template format")

    if has_title and not has_text and not has_file:
        return False, lang("Title provided but no text content found. Please either:\n• Enter text in the 'Original Text' field, OR\n• Upload a file using the template format")

    if not has_title and not has_text and has_file:
        if file_content and not is_template_format(file_content):
            return False, lang("Uploaded file does not follow the template format. Please:\n• Download the template file\n• Fill it with TITLE= and TEXT= markers\n• Upload the completed template")
        return True, None

    return True, None

def validate_text_content(text: str, min_words: int = 10) -> bool:
    if not text or not text.strip():
        raise ValueError(lang("Text content is empty."))
    words = text.split()
    word_count = len(words)
    if word_count < min_words:
        raise ValueError(
            lang(f"Text is too short for summarization. Please provide at least {min_words} words (currently: {word_count} words).")
        )
    meaningful_words = [w for w in words if len(w) > 2]
    if len(meaningful_words) < min_words // 2:
        raise ValueError(
            lang("Text contains insufficient meaningful content. Please provide more substantial text for summarization.")
        )
    return True
