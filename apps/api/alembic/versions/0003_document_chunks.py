"""pgvector document chunks for RAG

Revision ID: 0003_document_chunks
Revises: 0002_generation
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0003_document_chunks"
down_revision: Union[str, None] = "0002_generation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "position", name="uq_chunk_document_position"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_organization_id", "document_chunks", ["organization_id"])
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")
    op.drop_index("ix_document_chunks_organization_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
