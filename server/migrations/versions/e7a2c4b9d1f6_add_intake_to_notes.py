"""add intake to notes

Revision ID: e7a2c4b9d1f6
Revises: b4c7e1a9d2f3
Create Date: 2026-10-05 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e7a2c4b9d1f6"
down_revision: str | Sequence[str] | None = "b4c7e1a9d2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE notes ADD COLUMN intake JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE notes DROP COLUMN IF EXISTS intake")
