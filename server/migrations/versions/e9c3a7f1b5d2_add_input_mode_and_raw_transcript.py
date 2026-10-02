"""add input_mode and raw_transcript to dialogue_messages

Revision ID: e9c3a7f1b5d2
Revises: d4e8b2c7a1f3
Create Date: 2026-10-02 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e9c3a7f1b5d2"
down_revision: str | Sequence[str] | None = "d4e8b2c7a1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE dialogue_messages ADD COLUMN input_mode TEXT NOT NULL DEFAULT 'text' "
        "CHECK (input_mode IN ('text', 'voice'))"
    )
    op.execute("ALTER TABLE dialogue_messages ADD COLUMN raw_transcript TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE dialogue_messages DROP COLUMN IF EXISTS raw_transcript")
    op.execute("ALTER TABLE dialogue_messages DROP COLUMN IF EXISTS input_mode")
