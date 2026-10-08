"""add topic_edit to dialogue_messages

Revision ID: d1e7b3a9c5f2
Revises: c7a3e9f1d2b4
Create Date: 2026-10-08 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d1e7b3a9c5f2"
down_revision: str | Sequence[str] | None = "c7a3e9f1d2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE dialogue_messages ADD COLUMN topic_edit TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE dialogue_messages DROP COLUMN IF EXISTS topic_edit")
