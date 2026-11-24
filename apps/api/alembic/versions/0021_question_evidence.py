"""Question evidence and answer reference snapshots

Revision ID: 0021_question_evidence
Revises: 0020_chunk_metadata
Create Date: 2026-11-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_question_evidence"
down_revision: Union[str, None] = "0020_chunk_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "question_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("chapter", sa.String(length=240), nullable=True),
        sa.Column("section", sa.String(length=240), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("relevance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("model", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="generation"),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_question_evidence_organization_id", "question_evidence", ["organization_id"])
    op.create_index("ix_question_evidence_question_id", "question_evidence", ["question_id"])
    op.create_index("ix_question_evidence_document_id", "question_evidence", ["document_id"])
    op.create_index("ix_question_evidence_chunk_id", "question_evidence", ["chunk_id"])

    op.create_table(
        "answer_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_title", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("chapter", sa.String(length=240), nullable=True),
        sa.Column("section", sa.String(length=240), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attempt_id"], ["exam_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["question_evidence.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_answer_references_organization_id", "answer_references", ["organization_id"])
    op.create_index("ix_answer_references_attempt_id", "answer_references", ["attempt_id"])
    op.create_index("ix_answer_references_question_id", "answer_references", ["question_id"])
    op.create_index("ix_answer_references_document_id", "answer_references", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_answer_references_document_id", table_name="answer_references")
    op.drop_index("ix_answer_references_question_id", table_name="answer_references")
    op.drop_index("ix_answer_references_attempt_id", table_name="answer_references")
    op.drop_index("ix_answer_references_organization_id", table_name="answer_references")
    op.drop_table("answer_references")
    op.drop_index("ix_question_evidence_chunk_id", table_name="question_evidence")
    op.drop_index("ix_question_evidence_document_id", table_name="question_evidence")
    op.drop_index("ix_question_evidence_question_id", table_name="question_evidence")
    op.drop_index("ix_question_evidence_organization_id", table_name="question_evidence")
    op.drop_table("question_evidence")
