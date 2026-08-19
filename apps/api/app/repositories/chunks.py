from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import EMBEDDING_DIM
from app.core.pgvector import Vector
from app.models.chunk import DocumentChunk


class ChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_for_document(self, document_id: UUID, organization_id: UUID) -> int:
        result = await self.session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.organization_id == organization_id,
            )
        )
        return int(result or 0)

    async def replace(
        self,
        document_id: UUID,
        organization_id: UUID,
        chunks: list[DocumentChunk],
    ) -> None:
        await self.session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.organization_id == organization_id,
            )
        )
        if chunks:
            batch_size = 64
            for start in range(0, len(chunks), batch_size):
                self.session.add_all(chunks[start : start + batch_size])
                await self.session.flush()

    async def similar(
        self,
        document_id: UUID,
        organization_id: UUID,
        query: list[float],
        limit: int,
    ) -> list[DocumentChunk]:
        distance = DocumentChunk.embedding.cosine_distance(literal(query, Vector(EMBEDDING_DIM)))
        result = await self.session.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.organization_id == organization_id,
            )
            .order_by(distance)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_for_document(self, document_id: UUID, organization_id: UUID) -> list[DocumentChunk]:
        result = await self.session.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.organization_id == organization_id,
            )
            .order_by(DocumentChunk.position)
        )
        return list(result.scalars().all())
