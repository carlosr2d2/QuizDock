"""Academic appeals cases and evidence

Revision ID: 0023_appeals
Revises: 0022_document_chat
Create Date: 2026-11-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_appeals"
down_revision: Union[str, None] = "0022_document_chat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "appeal_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("student_argument", sa.Text(), nullable=False, server_default=""),
        sa.Column("selected_indices", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("correct_indices", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("system_evidence_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("question_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("exam_title", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attempt_id"], ["exam_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_appeal_cases_organization_id", "appeal_cases", ["organization_id"])
    op.create_index("ix_appeal_cases_attempt_id", "appeal_cases", ["attempt_id"])
    op.create_index("ix_appeal_cases_question_id", "appeal_cases", ["question_id"])
    op.create_index("ix_appeal_cases_exam_id", "appeal_cases", ["exam_id"])
    op.create_index("ix_appeal_cases_student_user_id", "appeal_cases", ["student_user_id"])
    op.create_index("ix_appeal_cases_status", "appeal_cases", ["status"])
    op.create_index(
        "uq_appeal_attempt_question",
        "appeal_cases",
        ["attempt_id", "question_id"],
        unique=True,
    )

    op.create_table(
        "appeal_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("appeal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitted_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("chapter", sa.String(length=240), nullable=True),
        sa.Column("section", sa.String(length=240), nullable=True),
        sa.Column("argument", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="student"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["appeal_id"], ["appeal_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_appeal_evidence_organization_id", "appeal_evidence", ["organization_id"])
    op.create_index("ix_appeal_evidence_appeal_id", "appeal_evidence", ["appeal_id"])
    op.create_index("ix_appeal_evidence_submitted_by_user_id", "appeal_evidence", ["submitted_by_user_id"])

    op.create_table(
        "appeal_resolutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("appeal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resolver_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("score_adjustment", sa.Float(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["appeal_id"], ["appeal_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolver_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("appeal_id", name="uq_appeal_resolutions_appeal_id"),
    )
    op.create_index("ix_appeal_resolutions_organization_id", "appeal_resolutions", ["organization_id"])
    op.create_index("ix_appeal_resolutions_appeal_id", "appeal_resolutions", ["appeal_id"])
    op.create_index("ix_appeal_resolutions_resolver_user_id", "appeal_resolutions", ["resolver_user_id"])

    op.create_table(
        "appeal_action_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("appeal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["appeal_id"], ["appeal_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_appeal_action_logs_organization_id", "appeal_action_logs", ["organization_id"])
    op.create_index("ix_appeal_action_logs_appeal_id", "appeal_action_logs", ["appeal_id"])
    op.create_index("ix_appeal_action_logs_actor_user_id", "appeal_action_logs", ["actor_user_id"])


def downgrade() -> None:
    op.drop_index("ix_appeal_action_logs_actor_user_id", table_name="appeal_action_logs")
    op.drop_index("ix_appeal_action_logs_appeal_id", table_name="appeal_action_logs")
    op.drop_index("ix_appeal_action_logs_organization_id", table_name="appeal_action_logs")
    op.drop_table("appeal_action_logs")
    op.drop_index("ix_appeal_resolutions_resolver_user_id", table_name="appeal_resolutions")
    op.drop_index("ix_appeal_resolutions_appeal_id", table_name="appeal_resolutions")
    op.drop_index("ix_appeal_resolutions_organization_id", table_name="appeal_resolutions")
    op.drop_table("appeal_resolutions")
    op.drop_index("ix_appeal_evidence_submitted_by_user_id", table_name="appeal_evidence")
    op.drop_index("ix_appeal_evidence_appeal_id", table_name="appeal_evidence")
    op.drop_index("ix_appeal_evidence_organization_id", table_name="appeal_evidence")
    op.drop_table("appeal_evidence")
    op.drop_index("uq_appeal_attempt_question", table_name="appeal_cases")
    op.drop_index("ix_appeal_cases_status", table_name="appeal_cases")
    op.drop_index("ix_appeal_cases_student_user_id", table_name="appeal_cases")
    op.drop_index("ix_appeal_cases_exam_id", table_name="appeal_cases")
    op.drop_index("ix_appeal_cases_question_id", table_name="appeal_cases")
    op.drop_index("ix_appeal_cases_attempt_id", table_name="appeal_cases")
    op.drop_index("ix_appeal_cases_organization_id", table_name="appeal_cases")
    op.drop_table("appeal_cases")
