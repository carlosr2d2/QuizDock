"""allow assigned members to download an exam as PDF

Revision ID: 0018_exam_pdf_download
Revises: 0017_subscriptions
Create Date: 2026-09-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_exam_pdf_download"
down_revision: Union[str, None] = "0017_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "exams",
        sa.Column("allow_pdf_download", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("exams", "allow_pdf_download", server_default=None)


def downgrade() -> None:
    op.drop_column("exams", "allow_pdf_download")
