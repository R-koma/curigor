"""add topic_correction to dialogue_messages

Revision ID: c5d8f2a1b7e9
Revises: 3b7e2c9d4f10
Create Date: 2026-10-06 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c5d8f2a1b7e9"
down_revision: str | Sequence[str] | None = "3b7e2c9d4f10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE dialogue_messages ADD COLUMN topic_correction_card JSONB")
    op.execute("ALTER TABLE dialogue_messages ADD COLUMN topic_correction_answer TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE dialogue_messages DROP COLUMN IF EXISTS topic_correction_answer")
    op.execute("ALTER TABLE dialogue_messages DROP COLUMN IF EXISTS topic_correction_card")
