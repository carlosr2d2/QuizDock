"""initial schema

Revision ID: 0002_generation
Revises: 0001_initial
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_generation"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("extracted_text", sa.Text(), nullable=True))
    op.add_column("exams", sa.Column("question_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("exams", sa.Column("credit_cost", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("exams", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("questions", sa.Column("position", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("credit_cost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("refunded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_generation_jobs_organization_id", "generation_jobs", ["organization_id"])
    op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_generation_jobs_status", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_organization_id", table_name="generation_jobs")
    op.drop_table("generation_jobs")
    op.drop_column("questions", "position")
    op.drop_column("exams", "error_message")
    op.drop_column("exams", "credit_cost")
    op.drop_column("exams", "question_count")
    op.drop_column("documents", "extracted_text")
