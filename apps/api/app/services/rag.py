from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.files import is_pdf
from app.models import Document
from app.models.chunk import DocumentChunk
from app.repositories.chunks import ChunkRepository
from app.services.chunking import chunk_text
from app.services.embeddings import cosine, embed_query, embed_texts
from app.services.exam_quality import polish_exam_text
from app.services.page_map import PageSpan, meta_for_chunk

settings = get_settings()


@dataclass(frozen=True)
class RetrievedContext:
    position: int
    content: str
    chunk_id: UUID | None = None
    page_start: int | None = None
    page_end: int | None = None
    chapter: str | None = None
    section: str | None = None
    relevance: float | None = None


class RagService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chunks = ChunkRepository(session)

    async def index_document(
        self,
        document: Document,
        *,
        pages: tuple[PageSpan, ...] | list[PageSpan] | None = None,
    ) -> int:
        text_body = document.extracted_text or ""
        spans = list(pages) if pages is not None else self._pages_for_document(document)
        pieces = [
            polish_exam_text(piece)
            for piece in chunk_text(
                text_body,
                size=settings.rag_chunk_size,
                overlap=settings.rag_chunk_overlap,
            )
        ]
        pieces = [piece for piece in pieces if piece]
        vectors = await embed_texts(pieces)
        model_name = _embedding_model_label()
        rows: list[DocumentChunk] = []
        search_from = 0
        for index, (piece, vector) in enumerate(zip(pieces, vectors, strict=True)):
            meta = meta_for_chunk(
                piece,
                full_text=text_body,
                spans=spans,
                search_from=search_from,
            )
            if meta.char_end is not None:
                search_from = max(search_from, meta.char_end - settings.rag_chunk_overlap)
            rows.append(
                DocumentChunk(
                    document_id=document.id,
                    organization_id=document.organization_id,
                    position=index,
                    content=piece,
                    embedding=vector,
                    page_start=meta.page_start,
                    page_end=meta.page_end,
                    chapter=meta.chapter,
                    section=meta.section,
                    char_start=meta.char_start,
                    char_end=meta.char_end,
                    embedding_model=model_name,
                    content_hash=meta.content_hash,
                )
            )
        await self.chunks.replace(document.id, document.organization_id, rows)
        await self.session.commit()
        return len(rows)

    async def ensure_indexed(self, document: Document) -> int:
        lock_id = int(document.id.hex[:8], 16) % (2**31)
        await self.session.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})
        try:
            count = await self.chunks.count_for_document(document.id, document.organization_id)
            if count > 0:
                return count
            return await self.index_document(document)
        finally:
            await self.session.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})

    async def contexts_for(
        self,
        document: Document,
        count: int,
        *,
        seed: UUID | int | None = None,
        exclude_positions: set[int] | None = None,
        query: str | None = None,
    ) -> list[RetrievedContext]:
        await self.ensure_indexed(document)
        effective_query = (query or "").strip() or _default_query(document)
        if settings.rag_semantic_enabled and effective_query:
            return await self.hybrid_retrieve(
                document.id,
                document.organization_id,
                count,
                query=effective_query,
                seed=seed,
                exclude_positions=exclude_positions,
            )
        return await self.retrieve_contexts(
            document.id,
            document.organization_id,
            count,
            seed=seed,
            exclude_positions=exclude_positions,
        )

    async def semantic_retrieve(
        self,
        document_id: UUID,
        organization_id: UUID,
        query: str,
        limit: int,
        *,
        exclude_positions: set[int] | None = None,
    ) -> list[RetrievedContext]:
        cleaned = query.strip()
        if not cleaned or limit <= 0:
            return []
        vector = await embed_query(cleaned)
        rows = await self.chunks.similar(document_id, organization_id, vector, limit=max(limit * 3, limit))
        excluded = exclude_positions or set()
        results: list[RetrievedContext] = []
        for row in rows:
            if row.position in excluded:
                continue
            results.append(
                _from_chunk(row, relevance=_relevance(vector, row.embedding))
            )
            if len(results) >= limit:
                break
        return results

    async def hybrid_retrieve(
        self,
        document_id: UUID,
        organization_id: UUID,
        count: int,
        *,
        query: str,
        seed: UUID | int | None = None,
        exclude_positions: set[int] | None = None,
    ) -> list[RetrievedContext]:
        if count <= 0:
            return []
        semantic_n = max(1, min(count, round(count * settings.rag_semantic_mix_ratio)))
        candidate_k = max(settings.rag_candidate_k, count * 2)
        semantic = await self.semantic_retrieve(
            document_id,
            organization_id,
            query,
            limit=min(candidate_k, max(semantic_n * 2, semantic_n)),
            exclude_positions=exclude_positions,
        )
        picked: list[RetrievedContext] = []
        used: set[int] = set(exclude_positions or ())
        for item in semantic:
            if item.position in used:
                continue
            picked.append(item)
            used.add(item.position)
            if len(picked) >= semantic_n:
                break

        if len(picked) < count:
            stratified = await self.retrieve_contexts(
                document_id,
                organization_id,
                count,
                seed=seed,
                exclude_positions=used,
            )
            for item in stratified:
                if item.position in used:
                    continue
                picked.append(item)
                used.add(item.position)
                if len(picked) >= count:
                    break

        if len(picked) < count:
            # Last resort: ignore exclusions except already picked.
            fallback = await self.retrieve_contexts(
                document_id,
                organization_id,
                count,
                seed=seed,
                exclude_positions=set(item.position for item in picked),
            )
            for item in fallback:
                if item.position in {row.position for row in picked}:
                    continue
                picked.append(item)
                if len(picked) >= count:
                    break

        return picked[:count]

    async def retrieve_contexts(
        self,
        document_id: UUID,
        organization_id: UUID,
        count: int,
        *,
        seed: UUID | int | None = None,
        exclude_positions: set[int] | None = None,
    ) -> list[RetrievedContext]:
        stored = await self.chunks.list_for_document(document_id, organization_id)
        if not stored:
            return []

        rng = random.Random(_seed_int(seed))
        excluded = exclude_positions or set()
        available = [chunk for chunk in stored if chunk.position not in excluded]
        if len(available) < count:
            available = list(stored)

        selected = _stratified_sample(available, count, rng)
        return [_from_chunk(chunk) for chunk in selected]

    def _pages_for_document(self, document: Document) -> list[PageSpan]:
        path = Path(settings.storage_dir) / document.storage_key
        if not path.is_file():
            return []
        try:
            from app.services.ingestion import extract_document

            extracted = extract_document(path, document.content_type)
            return list(extracted.pages)
        except Exception:
            if is_pdf(document.content_type, document.filename):
                return []
            return []


def _from_chunk(chunk: DocumentChunk, *, relevance: float | None = None) -> RetrievedContext:
    return RetrievedContext(
        position=chunk.position,
        content=chunk.content,
        chunk_id=getattr(chunk, "id", None),
        page_start=getattr(chunk, "page_start", None),
        page_end=getattr(chunk, "page_end", None),
        chapter=getattr(chunk, "chapter", None),
        section=getattr(chunk, "section", None),
        relevance=relevance,
    )


def _default_query(document: Document) -> str:
    title = (document.display_title or "").strip()
    if title:
        return title
    return (document.filename or "").strip()


def _embedding_model_label() -> str:
    if not settings.llm_api_key.strip():
        return "hashed-embedding"
    return settings.llm_embedding_model


def _relevance(query: list[float], embedding: list[float] | None) -> float | None:
    if not embedding:
        return None
    score = cosine(query, list(embedding))
    return max(0.0, min(1.0, (score + 1.0) / 2.0))


def _seed_int(seed: UUID | int | None) -> int:
    if seed is None:
        return random.randrange(2**31)
    if isinstance(seed, UUID):
        return seed.int % (2**31)
    return int(seed) % (2**31)


def _stratified_sample(chunks: list[DocumentChunk], k: int, rng: random.Random) -> list[DocumentChunk]:
    ordered = sorted(chunks, key=lambda chunk: chunk.position)
    if len(ordered) <= k:
        rng.shuffle(ordered)
        return ordered

    picked: list[DocumentChunk] = []
    size = len(ordered)
    for index in range(k):
        start = (index * size) // k
        end = max(start + 1, ((index + 1) * size) // k)
        group = ordered[start:end]
        ranked = sorted(group, key=lambda chunk: len(chunk.content), reverse=True)
        pool = ranked[: max(1, (len(ranked) + 1) // 2)]
        far = [chunk for chunk in pool if all(abs(chunk.position - other.position) > 1 for other in picked)]
        picked.append(rng.choice(far or pool))
    return picked
