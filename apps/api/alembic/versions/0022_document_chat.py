"""Document chat conversations and AI decision events

Revision ID: 0022_document_chat
Revises: 0021_question_evidence
Create Date: 2026-11-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_document_chat"
down_revision: Union[str, None] = "0021_question_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_document_conversations_organization_id", "document_conversations", ["organization_id"])
    op.create_index("ix_document_conversations_document_id", "document_conversations", ["document_id"])
    op.create_index("ix_document_conversations_user_id", "document_conversations", ["user_id"])
    op.create_index("ix_document_conversations_exam_id", "document_conversations", ["exam_id"])

    op.create_table(
        "document_chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("refusal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["document_conversations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_document_chat_messages_organization_id", "document_chat_messages", ["organization_id"])
    op.create_index("ix_document_chat_messages_conversation_id", "document_chat_messages", ["conversation_id"])

    op.create_table(
        "ai_decision_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("feature", sa.String(length=32), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column("chunk_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("relevance", sa.Float(), nullable=True),
        sa.Column("outcome", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_ai_decision_events_organization_id", "ai_decision_events", ["organization_id"])
    op.create_index("ix_ai_decision_events_actor_user_id", "ai_decision_events", ["actor_user_id"])
    op.create_index("ix_ai_decision_events_document_id", "ai_decision_events", ["document_id"])
    op.create_index("ix_ai_decision_events_conversation_id", "ai_decision_events", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_decision_events_conversation_id", table_name="ai_decision_events")
    op.drop_index("ix_ai_decision_events_document_id", table_name="ai_decision_events")
    op.drop_index("ix_ai_decision_events_actor_user_id", table_name="ai_decision_events")
    op.drop_index("ix_ai_decision_events_organization_id", table_name="ai_decision_events")
    op.drop_table("ai_decision_events")
    op.drop_index("ix_document_chat_messages_conversation_id", table_name="document_chat_messages")
    op.drop_index("ix_document_chat_messages_organization_id", table_name="document_chat_messages")
    op.drop_table("document_chat_messages")
    op.drop_index("ix_document_conversations_exam_id", table_name="document_conversations")
    op.drop_index("ix_document_conversations_user_id", table_name="document_conversations")
    op.drop_index("ix_document_conversations_document_id", table_name="document_conversations")
    op.drop_index("ix_document_conversations_organization_id", table_name="document_conversations")
    op.drop_table("document_conversations")
