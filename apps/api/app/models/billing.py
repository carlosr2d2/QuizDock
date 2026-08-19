from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


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
