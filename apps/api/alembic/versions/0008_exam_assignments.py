"""exam assignments for team workspaces

Revision ID: 0008_exam_assignments
Revises: 0007_invitations
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_exam_assignments"
down_revision: Union[str, None] = "0007_invitations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exam_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("exam_id", "user_id", name="uq_exam_assignment_user"),
    )
    op.create_index("ix_exam_assignments_organization_id", "exam_assignments", ["organization_id"])
    op.create_index("ix_exam_assignments_exam_id", "exam_assignments", ["exam_id"])
    op.create_index("ix_exam_assignments_user_id", "exam_assignments", ["user_id"])
    op.create_index("ix_exam_assignments_status", "exam_assignments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_exam_assignments_status", table_name="exam_assignments")
    op.drop_index("ix_exam_assignments_user_id", table_name="exam_assignments")
    op.drop_index("ix_exam_assignments_exam_id", table_name="exam_assignments")
    op.drop_index("ix_exam_assignments_organization_id", table_name="exam_assignments")
    op.drop_table("exam_assignments")
