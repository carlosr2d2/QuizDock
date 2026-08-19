"""add last_reviewed_at on flashcards

Revision ID: 0006_flashcard_last_reviewed
Revises: 0005_document_preview
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_flashcard_last_reviewed"
down_revision: Union[str, None] = "0005_document_preview"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("flashcards", sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("flashcards", "last_reviewed_at")
