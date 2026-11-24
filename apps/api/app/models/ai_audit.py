from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.exam import str_enum
from app.models.mixins import UUIDPrimaryKeyMixin, utcnow


class AiFeature(StrEnum):
    GENERATION = "generation"
    EVIDENCE = "evidence"
    CHAT = "chat"
    APPEAL_REVIEW = "appeal_review"


class AiDecisionEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_decision_events"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    feature: Mapped[AiFeature] = mapped_column(str_enum(AiFeature, "ai_feature", length=32))
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    conversation_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    model: Mapped[str] = mapped_column(String(120), default="")
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chunk_ids: Mapped[list] = mapped_column(JSONB, default=list)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    relevance: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome: Mapped[str] = mapped_column(String(64), default="")
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
