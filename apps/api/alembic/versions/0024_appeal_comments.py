"""Appeal comment thread

Revision ID: 0024_appeal_comments
Revises: 0023_appeals
Create Date: 2026-11-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_appeal_comments"
down_revision: Union[str, None] = "0023_appeals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "appeal_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("appeal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "attachment_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["appeal_id"], ["appeal_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_appeal_comments_organization_id", "appeal_comments", ["organization_id"])
    op.create_index("ix_appeal_comments_appeal_id", "appeal_comments", ["appeal_id"])
    op.create_index("ix_appeal_comments_author_user_id", "appeal_comments", ["author_user_id"])
    op.create_index(
        "ix_appeal_comments_appeal_created",
        "appeal_comments",
        ["appeal_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_appeal_comments_appeal_created", table_name="appeal_comments")
    op.drop_index("ix_appeal_comments_author_user_id", table_name="appeal_comments")
    op.drop_index("ix_appeal_comments_appeal_id", table_name="appeal_comments")
    op.drop_index("ix_appeal_comments_organization_id", table_name="appeal_comments")
    op.drop_table("appeal_comments")
