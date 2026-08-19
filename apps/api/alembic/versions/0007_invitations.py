"""organization invitations

Revision ID: 0007_invitations
Revises: 0006_flashcard_last_reviewed
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_invitations"
down_revision: Union[str, None] = "0006_flashcard_last_reviewed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invited_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_invitations_organization_id", "invitations", ["organization_id"])
    op.create_index("ix_invitations_invited_by_user_id", "invitations", ["invited_by_user_id"])
    op.create_index("ix_invitations_email", "invitations", ["email"])
    op.create_index("ix_invitations_token", "invitations", ["token"], unique=True)
    op.create_index("ix_invitations_status", "invitations", ["status"])
    op.create_index(
        "uq_invitations_org_email_pending",
        "invitations",
        ["organization_id", "email"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_invitations_org_email_pending", table_name="invitations")
    op.drop_index("ix_invitations_status", table_name="invitations")
    op.drop_index("ix_invitations_token", table_name="invitations")
    op.drop_index("ix_invitations_email", table_name="invitations")
    op.drop_index("ix_invitations_invited_by_user_id", table_name="invitations")
    op.drop_index("ix_invitations_organization_id", table_name="invitations")
    op.drop_table("invitations")
