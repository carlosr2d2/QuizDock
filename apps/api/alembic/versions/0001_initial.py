"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("plan", sa.String(32), nullable=False, server_default="free"),
        sa.Column("is_personal", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("credit_balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("locale", sa.String(8), nullable=False, server_default="es"),
        sa.Column("personal_organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["personal_organization_id"], ["organizations.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.create_index("ix_memberships_organization_id", "memberships", ["organization_id"])

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False, server_default="application/pdf"),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="uploaded"),
        sa.Column("language", sa.String(16), nullable=False, server_default="auto"),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_documents_organization_id", "documents", ["organization_id"])
    op.create_index("ix_documents_owner_user_id", "documents", ["owner_user_id"])
    op.create_index("ix_documents_status", "documents", ["status"])

    op.create_table(
        "exams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="quiz"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("time_limit_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_exams_organization_id", "exams", ["organization_id"])
    op.create_index("ix_exams_status", "exams", ["status"])

    op.create_table(
        "questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("correct_index", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_questions_exam_id", "questions", ["exam_id"])

    op.create_table(
        "exam_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answers", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "flashcards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("front", sa.Text(), nullable=False),
        sa.Column("back", sa.Text(), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("ease_factor", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "credit_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(120), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )


def downgrade() -> None:
    op.drop_table("credit_transactions")
    op.drop_table("flashcards")
    op.drop_table("exam_attempts")
    op.drop_table("questions")
    op.drop_table("exams")
    op.drop_table("documents")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("organizations")
