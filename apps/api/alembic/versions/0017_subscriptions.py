"""organization subscription period and payment order kind

Revision ID: 0017_subscriptions
Revises: 0016_audit_events
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_subscriptions"
down_revision: Union[str, None] = "0016_audit_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("plan_sku", sa.String(32), nullable=True))
    op.add_column("organizations", sa.Column("plan_renews_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "payment_orders",
        sa.Column("kind", sa.String(16), nullable=False, server_default="pack"),
    )


def downgrade() -> None:
    op.drop_column("payment_orders", "kind")
    op.drop_column("organizations", "plan_renews_at")
    op.drop_column("organizations", "plan_sku")
