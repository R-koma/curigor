"""drop_redundant_feedbacks_note_id_index

Revision ID: c4e9a1b7d205
Revises: 3b7e2c9d4f10
Create Date: 2026-10-06 13:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c4e9a1b7d205"
down_revision: str | Sequence[str] | None = "3b7e2c9d4f10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_feedbacks_note_id")


def downgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_feedbacks_note_id ON feedbacks(note_id)")
