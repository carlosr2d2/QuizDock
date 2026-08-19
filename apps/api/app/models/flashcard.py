from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Flashcard(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "flashcards"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
