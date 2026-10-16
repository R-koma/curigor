"""add turn_started_at to dialogue_sessions

Revision ID: a6d2f8c4e1b3
Revises: e4b7c1a9d2f6
Create Date: 2026-10-16 20:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a6d2f8c4e1b3"
down_revision: str | Sequence[str] | None = "e4b7c1a9d2f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE dialogue_sessions ADD COLUMN turn_started_at TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE dialogue_sessions DROP COLUMN IF EXISTS turn_started_at")
