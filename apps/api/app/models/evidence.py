from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.exam import str_enum
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class EvidenceSource(StrEnum):
    GENERATION = "generation"
    BACKFILL = "backfill"
    MANUAL = "manual"


class QuestionEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_evidence"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )
    chunk_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    quote: Mapped[str] = mapped_column(Text)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapter: Mapped[str | None] = mapped_column(String(240), nullable=True)
    section: Mapped[str | None] = mapped_column(String(240), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    relevance: Mapped[float] = mapped_column(Float, default=0.0)
    model: Mapped[str] = mapped_column(String(120), default="")
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[EvidenceSource] = mapped_column(
        str_enum(EvidenceSource, "evidence_source", length=32),
        default=EvidenceSource.GENERATION,
    )
    verified: Mapped[bool] = mapped_column(default=True)


class AnswerReference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "answer_references"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("exam_attempts.id", ondelete="CASCADE"),
        index=True,
    )
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
    )
    evidence_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("question_evidence.id", ondelete="SET NULL"),
        nullable=True,
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_title: Mapped[str] = mapped_column(String(240), default="")
    quote: Mapped[str] = mapped_column(Text)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapter: Mapped[str | None] = mapped_column(String(240), nullable=True)
    section: Mapped[str | None] = mapped_column(String(240), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
