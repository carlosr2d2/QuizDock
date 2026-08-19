from pathlib import Path
import re

_UUID_LIKE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
_TRAILING_ID = re.compile(r"[\s._-]+\d{3,}$")
_WORD_MIMES = {
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def document_kind(content_type: str | None, filename: str = "") -> str:
    suffix = Path(filename or "").suffix.lower()
    mime = (content_type or "").lower()
    if mime == "application/pdf" or suffix == ".pdf":
        return "pdf"
    if mime in {"text/markdown", "text/x-markdown"} or suffix in {".md", ".markdown"}:
        return "md"
    if mime.startswith("text/") or suffix == ".txt":
        return "txt"
    if mime in _WORD_MIMES or suffix in {".doc", ".docx"}:
        return "docx"
    return "file"


def is_pdf(content_type: str | None, filename: str = "") -> bool:
    return document_kind(content_type, filename) == "pdf"


def humanize_filename(filename: str) -> str:
    stem = Path(filename or "").stem
    stem = _UUID_LIKE.sub(" ", stem)
    stem = re.sub(r"[-_]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    stem = _TRAILING_ID.sub("", stem).strip()
    if not stem:
        return filename or "Documento"
    if stem.isupper() or stem.islower() or " " in stem:
        return stem.title()
    return stem[0].upper() + stem[1:]


def display_name(title: str | None, filename: str) -> str:
    cleaned = (title or "").strip()
    return cleaned or humanize_filename(filename)
