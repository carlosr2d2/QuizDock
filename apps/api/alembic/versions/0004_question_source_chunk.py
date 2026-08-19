"""store source chunk position on generated questions

Revision ID: 0004_question_source_chunk
Revises: 0003_document_chunks
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_question_source_chunk"
down_revision: Union[str, None] = "0003_document_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("source_chunk_position", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("questions", "source_chunk_position")
