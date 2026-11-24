"""Page and heading metadata helpers for chunk enrichment."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_CHAPTER = re.compile(
    r"^(?:cap[íi]tulo|chapter)\s+[\dIVXLCDM]+\b.*$",
    re.IGNORECASE,
)
_SECTION = re.compile(
    r"^(?:secci[oó]n|section|apartado)\s+[\dIVXLCDM]+\b.*$",
    re.IGNORECASE,
)
_NUMBERED_HEADING = re.compile(r"^\d+(?:\.\d+){0,3}\.?\s+\S.{2,120}$")


@dataclass(frozen=True)
class PageSpan:
    page: int
    text: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class ChunkMeta:
    page_start: int | None
    page_end: int | None
    chapter: str | None
    section: str | None
    char_start: int | None
    char_end: int | None
    content_hash: str


def build_page_spans(pages: list[str]) -> tuple[str, list[PageSpan]]:
    """Join non-empty page texts with blank lines and track char offsets."""
    spans: list[PageSpan] = []
    parts: list[str] = []
    cursor = 0
    for index, raw in enumerate(pages, start=1):
        text = (raw or "").strip()
        if not text:
            continue
        if parts:
            cursor += 2  # "\n\n" separator
        start = cursor
        end = start + len(text)
        spans.append(PageSpan(page=index, text=text, char_start=start, char_end=end))
        parts.append(text)
        cursor = end
    return "\n\n".join(parts), spans


def pages_for_range(spans: list[PageSpan], char_start: int, char_end: int) -> tuple[int | None, int | None]:
    if not spans or char_end <= char_start:
        return None, None
    overlapping = [
        span.page
        for span in spans
        if span.char_end > char_start and span.char_start < char_end
    ]
    if not overlapping:
        return None, None
    return overlapping[0], overlapping[-1]


def infer_heading(text: str, pattern: re.Pattern[str]) -> str | None:
    for line in text.splitlines()[:8]:
        candidate = " ".join(line.strip().split())
        if not candidate or len(candidate) > 160:
            continue
        if pattern.match(candidate):
            return candidate[:240]
    return None


def infer_chapter(text: str) -> str | None:
    return infer_heading(text, _CHAPTER) or infer_heading(text, _NUMBERED_HEADING)


def infer_section(text: str) -> str | None:
    return infer_heading(text, _SECTION)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def locate_chunk(full_text: str, chunk: str, *, start_at: int = 0) -> tuple[int | None, int | None]:
    """Best-effort locate chunk inside full text; returns (start, end) or (None, None)."""
    if not full_text or not chunk:
        return None, None
    exact = full_text.find(chunk, max(start_at, 0))
    if exact >= 0:
        return exact, exact + len(chunk)
    # Polished chunks may differ slightly; try a stable prefix.
    probe = chunk[: min(80, len(chunk))].strip()
    if len(probe) >= 24:
        found = full_text.find(probe, max(start_at, 0))
        if found >= 0:
            return found, min(found + len(chunk), len(full_text))
    return None, None


def meta_for_chunk(
    chunk: str,
    *,
    full_text: str,
    spans: list[PageSpan],
    search_from: int = 0,
) -> ChunkMeta:
    start, end = locate_chunk(full_text, chunk, start_at=search_from)
    page_start, page_end = (None, None)
    if start is not None and end is not None:
        page_start, page_end = pages_for_range(spans, start, end)
    return ChunkMeta(
        page_start=page_start,
        page_end=page_end,
        chapter=infer_chapter(chunk),
        section=infer_section(chunk),
        char_start=start,
        char_end=end,
        content_hash=content_hash(chunk),
    )
