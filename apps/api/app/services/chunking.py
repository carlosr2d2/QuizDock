import re

from app.services.exam_quality import normalize_extracted_text

_SPLIT = re.compile(r"\n\s*\n")
_SENTENCE = re.compile(r"(?<=[.!?…])\s+|(?<=[.!?…])\n+")
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
    """Split text into overlapping windows, preferring paragraphs then sentences."""
    normalized = normalize_extracted_text(text)
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
            windows.extend(_pack_sentences(_split_sentences(paragraph), size=size, overlap=overlap))
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


def _split_sentences(paragraph: str) -> list[str]:
    parts = [part.strip() for part in _SENTENCE.split(paragraph) if part.strip()]
    return parts or ([paragraph.strip()] if paragraph.strip() else [])


def _pack_sentences(sentences: list[str], *, size: int, overlap: int) -> list[str]:
    if not sentences:
        return []
    windows: list[str] = []
    index = 0
    while index < len(sentences):
        if len(sentences[index]) > size:
            windows.extend(_split_long_sentence(sentences[index], size=size, overlap=overlap))
            index += 1
            continue

        parts: list[str] = []
        length = 0
        cursor = index
        while cursor < len(sentences):
            sentence = sentences[cursor]
            if len(sentence) > size:
                break
            gap = 1 if parts else 0
            if parts and length + gap + len(sentence) > size:
                break
            parts.append(sentence)
            length += gap + len(sentence)
            cursor += 1

        if not parts:
            windows.extend(_split_long_sentence(sentences[index], size=size, overlap=overlap))
            index += 1
            continue

        windows.append(" ".join(parts))
        if cursor >= len(sentences):
            break
        next_index = _overlap_start(parts, cursor, overlap=overlap)
        index = max(next_index, index + 1)
    return windows


def _overlap_start(parts: list[str], end_index: int, *, overlap: int) -> int:
    """Return sentence index so the next window reuses ~overlap trailing chars."""
    if overlap <= 0 or not parts:
        return end_index
    chars = 0
    take = 0
    for sentence in reversed(parts):
        chars += len(sentence) + (1 if take else 0)
        take += 1
        if chars >= overlap:
            break
    return max(end_index - take, 0)


def _split_long_sentence(sentence: str, *, size: int, overlap: int) -> list[str]:
    """Last resort: cut on word boundaries when a single sentence exceeds size."""
    words = sentence.split()
    if not words:
        return []
    windows: list[str] = []
    start = 0
    while start < len(words):
        parts: list[str] = []
        length = 0
        cursor = start
        while cursor < len(words):
            word = words[cursor]
            gap = 1 if parts else 0
            if parts and length + gap + len(word) > size:
                break
            if not parts and len(word) > size:
                windows.append(word[:size])
                cursor += 1
                parts = []
                length = 0
                break
            parts.append(word)
            length += gap + len(word)
            cursor += 1
        if parts:
            windows.append(" ".join(parts))
        if cursor >= len(words):
            break
        if overlap <= 0:
            start = cursor
            continue
        # Step back a few words for overlap.
        back_chars = 0
        back = 0
        for word in reversed(parts):
            back_chars += len(word) + (1 if back else 0)
            back += 1
            if back_chars >= overlap:
                break
        start = max(cursor - back, start + 1)
    return windows
