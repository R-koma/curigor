"""add improvement_items to feedbacks

Revision ID: b4e7c2a9d1f3
Revises: f1b8d3a6c9e2
Create Date: 2026-10-06 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b4e7c2a9d1f3"
down_revision: str | Sequence[str] | None = "f1b8d3a6c9e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE feedbacks ADD COLUMN improvement_items JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE feedbacks DROP COLUMN IF EXISTS improvement_items")
