from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ErrorReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "error_reports"

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    path: Mapped[str] = mapped_column(String(500))
    message: Mapped[str] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open")
