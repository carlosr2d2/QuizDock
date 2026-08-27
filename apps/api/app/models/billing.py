from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PaymentStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class CreditTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_transactions"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(120))
    balance_after: Mapped[int] = mapped_column(Integer)


class PaymentOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payment_orders"
    __table_args__ = (
        UniqueConstraint("provider", "provider_session_id", name="uq_payment_order_provider_session"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    pack_id: Mapped[str] = mapped_column(String(32))
    credits: Mapped[int] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[PaymentStatus] = mapped_column(
        String(32),
        default=PaymentStatus.PENDING,
        index=True,
    )
    provider_session_id: Mapped[str | None] = mapped_column(String(191), nullable=True)
    provider_event_id: Mapped[str | None] = mapped_column(String(191), nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
