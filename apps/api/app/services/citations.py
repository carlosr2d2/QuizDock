"""Citation verification for document-grounded answers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from app.services.exam_quality import polish_exam_text

_SENTENCE = re.compile(r"(?<=[.!?…])\s+|\n+")
_TOKEN = re.compile(r"[a-záéíóúüñ0-9]{3,}", re.IGNORECASE)
_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class CitationResult:
    quote: str
    verified: bool
    confidence: float
    relevance: float
    page_start: int | None = None
    page_end: int | None = None
    chapter: str | None = None
    section: str | None = None
    chunk_id: UUID | None = None
    chunk_position: int | None = None


class CitationEngine:
    """Build a verifiable quote from a chunk; never invent page numbers."""

    def cite(
        self,
        *,
        chunk_content: str,
        chunk_id: UUID | None = None,
        chunk_position: int | None = None,
        page_start: int | None = None,
        page_end: int | None = None,
        chapter: str | None = None,
        section: str | None = None,
        anchor: str = "",
        claim: str = "",
        explanation: str = "",
        max_chars: int = 420,
    ) -> CitationResult | None:
        source = polish_exam_text(chunk_content or "").strip()
        if not source:
            return None

        quote, confidence = self._best_quote(
            source,
            anchor=anchor,
            claim=claim,
            explanation=explanation,
            max_chars=max_chars,
        )
        if not quote:
            return None

        relevance = self._relevance(quote, " ".join(part for part in (anchor, claim, explanation) if part))
        return CitationResult(
            quote=quote,
            verified=self._is_substring(quote, source),
            confidence=round(confidence, 4),
            relevance=round(relevance, 4),
            page_start=page_start,
            page_end=page_end,
            chapter=chapter,
            section=section,
            chunk_id=chunk_id,
            chunk_position=chunk_position,
        )

    def _best_quote(
        self,
        source: str,
        *,
        anchor: str,
        claim: str,
        explanation: str,
        max_chars: int,
    ) -> tuple[str, float]:
        for candidate, score in (
            (anchor, 0.95),
            (claim, 0.88),
            (explanation, 0.75),
        ):
            found = self._locate(candidate, source, max_chars=max_chars)
            if found:
                return found, score

        overlap = self._best_sentence_overlap(source, f"{anchor} {claim} {explanation}", max_chars=max_chars)
        if overlap:
            return overlap, 0.62

        excerpt = _WS.sub(" ", source).strip()[:max_chars].strip()
        if len(excerpt) < 24:
            return "", 0.0
        return excerpt, 0.4

    def _locate(self, needle: str, haystack: str, *, max_chars: int) -> str | None:
        cleaned = polish_exam_text(needle or "").strip()
        if len(cleaned) < 8:
            return None
        norm_hay = _normalize(haystack)
        norm_needle = _normalize(cleaned)
        index = norm_hay.find(norm_needle)
        if index < 0 and len(norm_needle) >= 24:
            index = norm_hay.find(norm_needle[: min(80, len(norm_needle))])
        if index < 0:
            return None
        # Map rough index back via original whitespace-collapsed window.
        window = _WS.sub(" ", haystack).strip()
        start = max(0, min(index, max(0, len(window) - 1)))
        end = min(len(window), start + max(len(cleaned), 24))
        quote = window[start:end].strip()
        if len(quote) > max_chars:
            quote = quote[:max_chars].rsplit(" ", 1)[0].strip() or quote[:max_chars]
        return quote if len(quote) >= 8 else None

    def _best_sentence_overlap(self, source: str, probe: str, *, max_chars: int) -> str | None:
        tokens = set(_tokens(probe))
        if not tokens:
            return None
        best = ""
        best_score = 0.0
        for sentence in _SENTENCE.split(source):
            text = _WS.sub(" ", sentence).strip()
            if len(text) < 24:
                continue
            overlap = len(tokens & set(_tokens(text))) / max(len(tokens), 1)
            if overlap > best_score:
                best_score = overlap
                best = text[:max_chars].strip()
        if best_score < 0.2 or len(best) < 24:
            return None
        return best

    def _relevance(self, quote: str, probe: str) -> float:
        left = set(_tokens(quote))
        right = set(_tokens(probe))
        if not left or not right:
            return 0.35 if quote else 0.0
        return len(left & right) / len(left | right)

    def _is_substring(self, quote: str, source: str) -> bool:
        return _normalize(quote) in _normalize(source)


def _normalize(value: str) -> str:
    return _WS.sub(" ", polish_exam_text(value).lower()).strip()


def _tokens(value: str) -> list[str]:
    return [token.lower() for token in _TOKEN.findall(value or "")]
