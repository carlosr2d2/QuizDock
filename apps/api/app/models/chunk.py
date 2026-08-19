from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import EMBEDDING_DIM
from app.core.db import Base
from app.core.pgvector import Vector
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DocumentChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("document_id", "position", name="uq_chunk_document_position"),)

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
