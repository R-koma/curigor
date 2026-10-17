"""add summary to study_memos

Revision ID: 3b8e5f1a7c94
Revises: d4b9e2c7a1f6
Create Date: 2026-10-17 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "3b8e5f1a7c94"
down_revision: str | Sequence[str] | None = "d4b9e2c7a1f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE study_memos ADD COLUMN summary TEXT NOT NULL DEFAULT ''")


def downgrade() -> None:
    op.execute("ALTER TABLE study_memos DROP COLUMN summary")
