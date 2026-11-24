from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.exam import str_enum
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class AppealStatus(StrEnum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    NEEDS_INFO = "needs_info"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CLOSED = "closed"


class AppealEvidenceSource(StrEnum):
    STUDENT = "student"
    SYSTEM = "system"
    TEACHER = "teacher"


class AppealDecision(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_INFO = "needs_info"


class AppealCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "appeal_cases"

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
    exam_id: Mapped[UUID] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"),
        index=True,
    )
    student_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[AppealStatus] = mapped_column(
        str_enum(AppealStatus, "appeal_status", length=32),
        default=AppealStatus.PENDING,
        index=True,
    )
    student_argument: Mapped[str] = mapped_column(Text, default="")
    selected_indices: Mapped[list] = mapped_column(JSONB, default=list)
    correct_indices: Mapped[list] = mapped_column(JSONB, default=list)
    system_evidence_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    question_prompt: Mapped[str] = mapped_column(Text, default="")
    exam_title: Mapped[str] = mapped_column(String(240), default="")


class AppealEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "appeal_evidence"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeal_cases.id", ondelete="CASCADE"),
        index=True,
    )
    submitted_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    chunk_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
    )
    quote: Mapped[str] = mapped_column(Text)
    page_start: Mapped[int | None] = mapped_column(nullable=True)
    page_end: Mapped[int | None] = mapped_column(nullable=True)
    chapter: Mapped[str | None] = mapped_column(String(240), nullable=True)
    section: Mapped[str | None] = mapped_column(String(240), nullable=True)
    argument: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[AppealEvidenceSource] = mapped_column(
        str_enum(AppealEvidenceSource, "appeal_evidence_source", length=32),
        default=AppealEvidenceSource.STUDENT,
    )


class AppealResolution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "appeal_resolutions"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeal_cases.id", ondelete="CASCADE"),
        index=True,
        unique=True,
    )
    resolver_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    decision: Mapped[AppealDecision] = mapped_column(
        str_enum(AppealDecision, "appeal_decision", length=32),
    )
    rationale: Mapped[str] = mapped_column(Text, default="")
    score_adjustment: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppealActionLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "appeal_action_logs"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeal_cases.id", ondelete="CASCADE"),
        index=True,
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppealComment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "appeal_comments"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeal_cases.id", ondelete="CASCADE"),
        index=True,
    )
    author_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    body: Mapped[str] = mapped_column(Text, default="")
    attachment_keys: Mapped[list] = mapped_column(JSONB, default=list)
