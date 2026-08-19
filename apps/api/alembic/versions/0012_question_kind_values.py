"""normalize question.kind to StrEnum values

Revision ID: 0012_question_kind_values
Revises: 0011_error_reports
Create Date: 2026-08-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012_question_kind_values"
down_revision: Union[str, None] = "0011_error_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE questions SET kind = CASE kind
                WHEN 'TRUE_FALSE' THEN 'true_false'
                WHEN 'SINGLE_CHOICE' THEN 'single_choice'
                WHEN 'MULTIPLE_CHOICE' THEN 'multiple_choice'
                ELSE kind
            END
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE questions SET kind = CASE kind
                WHEN 'true_false' THEN 'TRUE_FALSE'
                WHEN 'single_choice' THEN 'SINGLE_CHOICE'
                WHEN 'multiple_choice' THEN 'MULTIPLE_CHOICE'
                ELSE kind
            END
            """
        )
    )
