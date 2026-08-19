"""progress counter while an exam is generating

Revision ID: 0010_exam_generated_count
Revises: 0009_question_kinds
Create Date: 2026-08-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_exam_generated_count"
down_revision: Union[str, None] = "0009_question_kinds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "exams",
        sa.Column("generated_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        sa.text(
            "UPDATE exams SET generated_count = question_count "
            "WHERE status NOT IN ('generating', 'draft', 'failed')"
        )
    )
    op.alter_column("exams", "generated_count", server_default=None)


def downgrade() -> None:
    op.drop_column("exams", "generated_count")
