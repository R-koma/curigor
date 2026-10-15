"""add prompt_fingerprint to notes, feedbacks and note_revisions

Revision ID: c3f8a1d5e7b9
Revises: c3f8a2d6e9b1
Create Date: 2026-10-15 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3f8a1d5e7b9"
down_revision: str | Sequence[str] | None = "c3f8a2d6e9b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("notes", "feedbacks", "note_revisions")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("prompt_fingerprint", sa.Text(), nullable=True))


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "prompt_fingerprint")
