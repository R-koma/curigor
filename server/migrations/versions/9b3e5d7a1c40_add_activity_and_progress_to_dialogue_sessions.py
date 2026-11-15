"""add activity and progress to dialogue sessions

Revision ID: 9b3e5d7a1c40
Revises: 84cac66387cc
Create Date: 2026-11-15 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "9b3e5d7a1c40"
down_revision: str | Sequence[str] | None = "84cac66387cc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE dialogue_sessions ADD COLUMN last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")
    op.execute("UPDATE dialogue_sessions SET last_activity_at = COALESCE(ended_at, started_at)")
    op.execute("ALTER TABLE dialogue_sessions ADD COLUMN progress_reached INTEGER")
    op.execute("ALTER TABLE dialogue_sessions ADD COLUMN progress_target INTEGER")


def downgrade() -> None:
    op.execute("ALTER TABLE dialogue_sessions DROP COLUMN IF EXISTS progress_target")
    op.execute("ALTER TABLE dialogue_sessions DROP COLUMN IF EXISTS progress_reached")
    op.execute("ALTER TABLE dialogue_sessions DROP COLUMN IF EXISTS last_activity_at")
