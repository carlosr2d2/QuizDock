from dataclasses import dataclass
from io import BytesIO
from pathlib import Path


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    page_count: int
    metadata_title: str | None = None


def extract_document(path: Path, content_type: str) -> ExtractedDocument:
    """Return extracted text, page count, and PDF metadata title when present."""
    data = path.read_bytes()
    suffix = path.suffix.lower()
    is_pdf = content_type == "application/pdf" or suffix == ".pdf"
    if is_pdf:
        return _extract_pdf(data)
    text = _decode_text(data).strip()
    return ExtractedDocument(text=text, page_count=1 if text else 0)


def pdf_metadata_title(path: Path) -> str | None:
    try:
        return _extract_pdf(path.read_bytes()).metadata_title
    except Exception:
        return None


def _extract_pdf(data: bytes) -> ExtractedDocument:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(part.strip() for part in pages if part.strip())
    return ExtractedDocument(
        text=text.strip(),
        page_count=len(reader.pages),
        metadata_title=_pdf_title(reader),
    )


def _pdf_title(reader: object) -> str | None:
    metadata = getattr(reader, "metadata", None)
    if metadata is None:
        return None
    raw = getattr(metadata, "title", None)
    if not raw and hasattr(metadata, "get"):
        raw = metadata.get("/Title")
    if not isinstance(raw, str):
        return None
    title = " ".join(raw.split()).strip()
    return title or None


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")
