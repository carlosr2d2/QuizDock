from __future__ import annotations

import random
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Document
from app.models.chunk import DocumentChunk
from app.repositories.chunks import ChunkRepository
from app.services.chunking import chunk_text
from app.services.embeddings import embed_texts
from app.services.exam_quality import polish_exam_text

settings = get_settings()


@dataclass(frozen=True)
class RetrievedContext:
    position: int
    content: str


class RagService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chunks = ChunkRepository(session)

    async def index_document(self, document: Document) -> int:
        text = document.extracted_text or ""
        pieces = [
            polish_exam_text(piece)
            for piece in chunk_text(
                text,
                size=settings.rag_chunk_size,
                overlap=settings.rag_chunk_overlap,
            )
        ]
        pieces = [piece for piece in pieces if piece]
        vectors = await embed_texts(pieces)
        rows = [
            DocumentChunk(
                document_id=document.id,
                organization_id=document.organization_id,
                position=index,
                content=piece,
                embedding=vector,
            )
            for index, (piece, vector) in enumerate(zip(pieces, vectors, strict=True))
        ]
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
    ) -> list[RetrievedContext]:
        await self.ensure_indexed(document)
        return await self.retrieve_contexts(
            document.id,
            document.organization_id,
            count,
            seed=seed,
            exclude_positions=exclude_positions,
        )

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
        return [RetrievedContext(position=chunk.position, content=chunk.content) for chunk in selected]


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
