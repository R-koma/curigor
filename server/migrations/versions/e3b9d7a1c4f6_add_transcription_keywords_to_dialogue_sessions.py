"""add transcription keywords to dialogue_sessions

Revision ID: e3b9d7a1c4f6
Revises: c7e1a9d3f5b2
Create Date: 2026-10-13 18:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e3b9d7a1c4f6"
down_revision: str | Sequence[str] | None = "c7e1a9d3f5b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE dialogue_sessions ADD COLUMN transcription_keywords TEXT[]")
    op.execute("ALTER TABLE dialogue_sessions ADD COLUMN transcription_keywords_source TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE dialogue_sessions DROP COLUMN IF EXISTS transcription_keywords_source")
    op.execute("ALTER TABLE dialogue_sessions DROP COLUMN IF EXISTS transcription_keywords")
