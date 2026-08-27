"""payment orders and billing country

Revision ID: 0015_payments
Revises: 0014_password_reset
Create Date: 2026-08-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_payments"
down_revision: Union[str, None] = "0014_password_reset"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("billing_country", sa.String(2), nullable=False, server_default="CO"),
    )
    op.create_table(
        "payment_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("pack_id", sa.String(32), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("provider_session_id", sa.String(191), nullable=True),
        sa.Column("provider_event_id", sa.String(191), nullable=True),
        sa.Column("checkout_url", sa.String(500), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("provider", "provider_session_id", name="uq_payment_order_provider_session"),
    )
    op.create_index("ix_payment_orders_organization_id", "payment_orders", ["organization_id"])
    op.create_index("ix_payment_orders_user_id", "payment_orders", ["user_id"])
    op.create_index("ix_payment_orders_provider", "payment_orders", ["provider"])
    op.create_index("ix_payment_orders_status", "payment_orders", ["status"])


def downgrade() -> None:
    op.drop_index("ix_payment_orders_status", table_name="payment_orders")
    op.drop_index("ix_payment_orders_provider", table_name="payment_orders")
    op.drop_index("ix_payment_orders_user_id", table_name="payment_orders")
    op.drop_index("ix_payment_orders_organization_id", table_name="payment_orders")
    op.drop_table("payment_orders")
    op.drop_column("organizations", "billing_country")
