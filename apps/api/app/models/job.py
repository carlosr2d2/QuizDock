from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class GenerationJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tracks async flashcard (and similar) generation so the client can poll."""

    __tablename__ = "generation_jobs"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    credit_cost: Mapped[int] = mapped_column(Integer, default=0)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    result_id: Mapped[UUID | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    refunded: Mapped[bool] = mapped_column(default=False)
