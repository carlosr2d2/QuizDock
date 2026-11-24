"""Appeal AI recommendations

Revision ID: 0025_appeal_ai
Revises: 0024_appeal_comments
Create Date: 2026-11-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025_appeal_ai"
down_revision: Union[str, None] = "0024_appeal_comments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "appeal_ai_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("appeal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("recommendation", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("ambiguity", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "alt_chunk_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("system_quote", sa.Text(), nullable=True),
        sa.Column("student_quote", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("credit_cost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["appeal_id"], ["appeal_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_appeal_ai_recommendations_organization_id", "appeal_ai_recommendations", ["organization_id"])
    op.create_index("ix_appeal_ai_recommendations_appeal_id", "appeal_ai_recommendations", ["appeal_id"])
    op.create_index(
        "ix_appeal_ai_recommendations_requested_by_user_id",
        "appeal_ai_recommendations",
        ["requested_by_user_id"],
    )
    op.create_index("ix_appeal_ai_recommendations_status", "appeal_ai_recommendations", ["status"])

    op.add_column(
        "appeal_resolutions",
        sa.Column("ai_recommendation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_appeal_resolutions_ai_recommendation_id",
        "appeal_resolutions",
        "appeal_ai_recommendations",
        ["ai_recommendation_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_appeal_resolutions_ai_recommendation_id", "appeal_resolutions", type_="foreignkey")
    op.drop_column("appeal_resolutions", "ai_recommendation_id")
    op.drop_index("ix_appeal_ai_recommendations_status", table_name="appeal_ai_recommendations")
    op.drop_index("ix_appeal_ai_recommendations_requested_by_user_id", table_name="appeal_ai_recommendations")
    op.drop_index("ix_appeal_ai_recommendations_appeal_id", table_name="appeal_ai_recommendations")
    op.drop_index("ix_appeal_ai_recommendations_organization_id", table_name="appeal_ai_recommendations")
    op.drop_table("appeal_ai_recommendations")
