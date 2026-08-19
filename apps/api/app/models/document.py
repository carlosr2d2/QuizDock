from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    display_title: Mapped[str | None] = mapped_column(String(240), nullable=True)
    content_type: Mapped[str] = mapped_column(String(120), default="application/pdf")
    storage_key: Mapped[str] = mapped_column(String(500))
    cover_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", native_enum=False, length=32),
        default=DocumentStatus.UPLOADED,
        index=True,
    )
    language: Mapped[str] = mapped_column(String(16), default="auto")
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
