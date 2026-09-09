from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TypeVar
from uuid import UUID

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

E = TypeVar("E", bound=StrEnum)


def parse_str_enum(enum_cls: type[E], value: object) -> E:
    if isinstance(value, enum_cls):
        return value
    raw = str(value or "").strip()
    try:
        return enum_cls(raw)
    except ValueError:
        pass
    by_name = {item.name: item for item in enum_cls}
    by_value = {item.value: item for item in enum_cls}
    found = by_name.get(raw) or by_value.get(raw.lower())
    if found is None:
        raise LookupError(f"{raw!r} is not a valid {enum_cls.__name__}")
    return found


class StrEnumType(TypeDecorator):
    """Persist StrEnum values; accept legacy member names already in the database."""

    impl = String
    cache_ok = True

    def __init__(self, enum_cls: type[StrEnum], length: int = 32):
        super().__init__(length=length)
        self.enum_cls = enum_cls

    def process_bind_param(self, value: object, dialect) -> str | None:
        if value is None:
            return None
        return parse_str_enum(self.enum_cls, value).value

    def process_result_value(self, value: object, dialect) -> StrEnum | None:
        if value is None:
            return None
        return parse_str_enum(self.enum_cls, value)


def str_enum(enum_cls: type[StrEnum], _name: str, length: int = 32) -> StrEnumType:
    return StrEnumType(enum_cls, length=length)


class ExamKind(StrEnum):
    QUIZ = "quiz"
    EXAM = "exam"


class ExamStatus(StrEnum):
    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    ASSIGNED = "assigned"
    ARCHIVED = "archived"
    FAILED = "failed"


class QuestionKind(StrEnum):
    TRUE_FALSE = "true_false"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"

    @classmethod
    def parse(cls, value: object) -> QuestionKind:
        try:
            return parse_str_enum(cls, value)
        except LookupError:
            return cls.SINGLE_CHOICE


class Question(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "questions"

    exam_id: Mapped[UUID] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    kind: Mapped[QuestionKind] = mapped_column(
        str_enum(QuestionKind, "question_kind"),
        default=QuestionKind.SINGLE_CHOICE,
    )
    options: Mapped[list[str]] = mapped_column(JSONB)
    correct_index: Mapped[int] = mapped_column(Integer)
    correct_indices: Mapped[list[int]] = mapped_column(JSONB, default=list)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(16), default="medium")
    position: Mapped[int] = mapped_column(Integer, default=0)
    source_chunk_position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    exam: Mapped[Exam] = relationship(back_populates="questions")


class Exam(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exams"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(240))
    kind: Mapped[ExamKind] = mapped_column(
        Enum(ExamKind, name="exam_kind", native_enum=False, length=32),
        default=ExamKind.QUIZ,
    )
    status: Mapped[ExamStatus] = mapped_column(
        Enum(ExamStatus, name="exam_status", native_enum=False, length=32),
        default=ExamStatus.DRAFT,
        index=True,
    )
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    generated_count: Mapped[int] = mapped_column(Integer, default=0)
    credit_cost: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    allow_pdf_download: Mapped[bool] = mapped_column(default=False)

    questions: Mapped[list[Question]] = relationship(back_populates="exam", order_by="Question.position")


class ExamAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exam_attempts"

    exam_id: Mapped[UUID] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answers: Mapped[dict] = mapped_column(JSONB, default=dict)


class AssignmentStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


class ExamAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exam_assignments"
    __table_args__ = (UniqueConstraint("exam_id", "user_id", name="uq_exam_assignment_user"),)

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    exam_id: Mapped[UUID] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    assigned_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, name="assignment_status", native_enum=False, length=32),
        default=AssignmentStatus.PENDING,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExamGroupAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exam_group_assignments"
    __table_args__ = (UniqueConstraint("exam_id", "group_id", name="uq_exam_group_assignment"),)

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    exam_id: Mapped[UUID] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    assigned_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
