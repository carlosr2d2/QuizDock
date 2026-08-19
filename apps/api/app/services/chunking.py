import re

_SPLIT = re.compile(r"\n\s*\n")
_TOC_DOTS = re.compile(r"\.{4,}\s*\d+\s*$")
_TRAILING_PAGE = re.compile(r"\s+\d{1,4}\s*$")


def is_low_quality_chunk(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return True
    toc_hits = sum(
        1
        for line in lines
        if _TOC_DOTS.search(line) or (len(line) < 80 and _TRAILING_PAGE.search(line))
    )
    if len(lines) >= 5 and toc_hits / len(lines) >= 0.45:
        return True
    letters = sum(character.isalpha() for character in text)
    return letters / max(len(text), 1) < 0.28


def chunk_text(text: str, size: int = 1200, overlap: int = 200, min_chars: int = 80) -> list[str]:
    """Split text into overlapping windows, preferring paragraph boundaries."""
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []

    paragraphs = [part.strip() for part in _SPLIT.split(normalized) if part.strip()]
    windows: list[str] = []
    buffer = ""

    def flush() -> None:
        nonlocal buffer
        if buffer.strip():
            windows.append(buffer.strip())
        buffer = ""

    for paragraph in paragraphs:
        if len(paragraph) > size:
            flush()
            start = 0
            while start < len(paragraph):
                end = min(start + size, len(paragraph))
                windows.append(paragraph[start:end].strip())
                if end == len(paragraph):
                    break
                start = max(end - overlap, start + 1)
            continue
        candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
        if len(candidate) <= size:
            buffer = candidate
        else:
            flush()
            buffer = paragraph
    flush()

    chunks = [item for item in windows if len(item) >= min_chars]
    quality = [item for item in chunks if not is_low_quality_chunk(item)]
    return quality or chunks or ([normalized[:size]] if normalized else [])
