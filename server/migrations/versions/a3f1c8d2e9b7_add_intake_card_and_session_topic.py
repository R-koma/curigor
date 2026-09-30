"""add intake_card and session topic

Revision ID: a3f1c8d2e9b7
Revises: ff0adafc9666
Create Date: 2026-09-30 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a3f1c8d2e9b7"
down_revision: str | Sequence[str] | None = "ff0adafc9666"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE dialogue_messages ADD COLUMN intake_card JSONB")
    op.execute("ALTER TABLE dialogue_sessions ADD COLUMN topic TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE dialogue_sessions DROP COLUMN IF EXISTS topic")
    op.execute("ALTER TABLE dialogue_messages DROP COLUMN IF EXISTS intake_card")
