"""true/false and multi-correct question kinds

Revision ID: 0009_question_kinds
Revises: 0008_exam_assignments
Create Date: 2026-08-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_question_kinds"
down_revision: Union[str, None] = "0008_exam_assignments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("kind", sa.String(32), nullable=False, server_default="single_choice"),
    )
    op.add_column("questions", sa.Column("correct_indices", postgresql.JSONB(), nullable=True))
    op.execute(sa.text("UPDATE questions SET correct_indices = jsonb_build_array(correct_index)"))
    op.alter_column("questions", "correct_indices", nullable=False)
    op.alter_column("questions", "kind", server_default=None)


def downgrade() -> None:
    op.drop_column("questions", "correct_indices")
    op.drop_column("questions", "kind")
