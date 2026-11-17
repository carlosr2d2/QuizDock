"""track last time a member entered a workspace

Revision ID: 0019_membership_last_seen
Revises: 0018_exam_pdf_download
Create Date: 2026-11-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_membership_last_seen"
down_revision: Union[str, None] = "0018_exam_pdf_download"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "memberships",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("memberships", "last_seen_at")
