"""Add page/chapter metadata to document chunks

Revision ID: 0020_chunk_metadata
Revises: 0019_membership_last_seen
Create Date: 2026-11-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_chunk_metadata"
down_revision: Union[str, None] = "0019_membership_last_seen"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("page_start", sa.Integer(), nullable=True))
    op.add_column("document_chunks", sa.Column("page_end", sa.Integer(), nullable=True))
    op.add_column("document_chunks", sa.Column("chapter", sa.String(length=240), nullable=True))
    op.add_column("document_chunks", sa.Column("section", sa.String(length=240), nullable=True))
    op.add_column("document_chunks", sa.Column("char_start", sa.Integer(), nullable=True))
    op.add_column("document_chunks", sa.Column("char_end", sa.Integer(), nullable=True))
    op.add_column("document_chunks", sa.Column("embedding_model", sa.String(length=120), nullable=True))
    op.add_column("document_chunks", sa.Column("content_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("document_chunks", "content_hash")
    op.drop_column("document_chunks", "embedding_model")
    op.drop_column("document_chunks", "char_end")
    op.drop_column("document_chunks", "char_start")
    op.drop_column("document_chunks", "section")
    op.drop_column("document_chunks", "chapter")
    op.drop_column("document_chunks", "page_end")
    op.drop_column("document_chunks", "page_start")
