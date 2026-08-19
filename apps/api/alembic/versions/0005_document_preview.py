"""store display title and cover thumbnail key on documents

Revision ID: 0005_document_preview
Revises: 0004_question_source_chunk
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_document_preview"
down_revision: Union[str, None] = "0004_question_source_chunk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("display_title", sa.String(length=240), nullable=True))
    op.add_column("documents", sa.Column("cover_key", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "cover_key")
    op.drop_column("documents", "display_title")
