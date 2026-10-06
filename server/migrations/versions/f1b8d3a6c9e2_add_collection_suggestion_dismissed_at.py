"""add collection_suggestion_dismissed_at to notes

Revision ID: f1b8d3a6c9e2
Revises: c5d8f2a1b7e9
Create Date: 2026-10-06 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1b8d3a6c9e2"
down_revision: str | Sequence[str] | None = "c5d8f2a1b7e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE notes ADD COLUMN collection_suggestion_dismissed_at TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE notes DROP COLUMN IF EXISTS collection_suggestion_dismissed_at")
