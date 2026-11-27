from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from app.services.exam_quality import normalize_extracted_text
from app.services.page_map import PageSpan, build_page_spans


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    page_count: int
    metadata_title: str | None = None
    pages: tuple[PageSpan, ...] = ()


def extract_document(path: Path, content_type: str) -> ExtractedDocument:
    """Return extracted text, page count, and PDF metadata title when present."""
    data = path.read_bytes()
    suffix = path.suffix.lower()
    is_pdf = content_type == "application/pdf" or suffix == ".pdf"
    if is_pdf:
        return _extract_pdf(data)
    text = normalize_extracted_text(_decode_text(data))
    if not text:
        return ExtractedDocument(text="", page_count=0)
    joined, spans = build_page_spans([text])
    return ExtractedDocument(text=joined, page_count=1, pages=tuple(spans))


def pdf_metadata_title(path: Path) -> str | None:
    try:
        return _extract_pdf(path.read_bytes()).metadata_title
    except Exception:
        return None


def _extract_pdf(data: bytes) -> ExtractedDocument:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    raw_pages = [normalize_extracted_text(page.extract_text() or "") for page in reader.pages]
    text, spans = build_page_spans(raw_pages)
    return ExtractedDocument(
        text=text,
        page_count=len(reader.pages),
        metadata_title=_pdf_title(reader),
        pages=tuple(spans),
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
