"""add intake_answers to dialogue_messages

Revision ID: b4c7e1a9d2f3
Revises: d9a3e5f7c2b6
Create Date: 2026-10-04 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b4c7e1a9d2f3"
down_revision: str | Sequence[str] | None = "d9a3e5f7c2b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE dialogue_messages ADD COLUMN intake_answers JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE dialogue_messages DROP COLUMN IF EXISTS intake_answers")
