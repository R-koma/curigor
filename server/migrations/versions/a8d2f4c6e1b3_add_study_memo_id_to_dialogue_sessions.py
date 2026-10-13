"""link learning sessions to the study memo they started from

Revision ID: a8d2f4c6e1b3
Revises: f7c1a9e3d5b2
Create Date: 2026-10-14 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a8d2f4c6e1b3"
down_revision: str | Sequence[str] | None = "f7c1a9e3d5b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE dialogue_sessions ADD COLUMN study_memo_id UUID REFERENCES study_memos(id) ON DELETE SET NULL"
    )
    op.execute(
        "CREATE INDEX idx_dialogue_sessions_study_memo_id ON dialogue_sessions(study_memo_id) "
        "WHERE study_memo_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_dialogue_sessions_study_memo_id")
    op.execute("ALTER TABLE dialogue_sessions DROP COLUMN IF EXISTS study_memo_id")
