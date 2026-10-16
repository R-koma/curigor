"""add generation_started_at to dialogue_sessions

Revision ID: d7a3f9c2e5b8
Revises: b8e4d2a6c1f9
Create Date: 2026-10-16 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d7a3f9c2e5b8"
down_revision: str | Sequence[str] | None = "b8e4d2a6c1f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE dialogue_sessions ADD COLUMN generation_started_at TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE dialogue_sessions DROP COLUMN IF EXISTS generation_started_at")
