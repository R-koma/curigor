"""add is_trial to dialogue_sessions

Revision ID: a4c8e2f6b1d3
Revises: d1e7b3a9c5f2
Create Date: 2026-10-08 18:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a4c8e2f6b1d3"
down_revision: str | Sequence[str] | None = "d1e7b3a9c5f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE dialogue_sessions ADD COLUMN is_trial BOOLEAN NOT NULL DEFAULT false")


def downgrade() -> None:
    op.execute("ALTER TABLE dialogue_sessions DROP COLUMN IF EXISTS is_trial")
