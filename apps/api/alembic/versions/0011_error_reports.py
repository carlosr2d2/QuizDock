"""client error reports for the support team

Revision ID: 0011_error_reports
Revises: 0010_exam_generated_count
Create Date: 2026-08-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_error_reports"
down_revision: Union[str, None] = "0010_exam_generated_count"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "error_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_error_reports_user_id", "error_reports", ["user_id"])
    op.create_index("ix_error_reports_organization_id", "error_reports", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_error_reports_organization_id", table_name="error_reports")
    op.drop_index("ix_error_reports_user_id", table_name="error_reports")
    op.drop_table("error_reports")
