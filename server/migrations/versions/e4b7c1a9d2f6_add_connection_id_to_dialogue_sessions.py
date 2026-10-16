"""add connection_id to dialogue_sessions

Revision ID: e4b7c1a9d2f6
Revises: d7a3f9c2e5b8
Create Date: 2026-10-16 18:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e4b7c1a9d2f6"
down_revision: str | Sequence[str] | None = "d7a3f9c2e5b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE dialogue_sessions ADD COLUMN connection_id UUID")


def downgrade() -> None:
    op.execute("ALTER TABLE dialogue_sessions DROP COLUMN IF EXISTS connection_id")
