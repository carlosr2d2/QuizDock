from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.exam import str_enum
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class DocumentConversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_conversations"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    exam_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("exams.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(240), nullable=True)


class DocumentChatMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_chat_messages"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_conversations.id", ondelete="CASCADE"),
        index=True,
    )
    role: Mapped[ChatRole] = mapped_column(str_enum(ChatRole, "chat_role", length=16))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSONB, default=list)
    refusal: Mapped[bool] = mapped_column(Boolean, default=False)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
