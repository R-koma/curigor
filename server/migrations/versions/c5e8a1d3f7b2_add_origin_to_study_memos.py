"""add origin to study_memos

Revision ID: c5e8a1d3f7b2
Revises: 3b8e5f1a7c94
Create Date: 2026-10-18 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c5e8a1d3f7b2"
down_revision: str | Sequence[str] | None = "3b8e5f1a7c94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE study_memos ADD COLUMN origin_note_id UUID REFERENCES notes(id) ON DELETE SET NULL")
    op.execute(
        "ALTER TABLE study_memos ADD COLUMN origin_feedback_id UUID REFERENCES feedbacks(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE study_memos ADD COLUMN origin_improvement_index INT")
    op.execute("ALTER TABLE study_memos ADD COLUMN origin_improvement TEXT")
    op.execute("ALTER TABLE study_memos ADD COLUMN origin_aspect_id TEXT")
    op.execute(
        "CREATE INDEX idx_study_memos_origin_note_id ON study_memos(user_id, origin_note_id) "
        "WHERE origin_note_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_study_memos_origin_note_id")
    op.execute("ALTER TABLE study_memos DROP COLUMN IF EXISTS origin_aspect_id")
    op.execute("ALTER TABLE study_memos DROP COLUMN IF EXISTS origin_improvement")
    op.execute("ALTER TABLE study_memos DROP COLUMN IF EXISTS origin_improvement_index")
    op.execute("ALTER TABLE study_memos DROP COLUMN IF EXISTS origin_feedback_id")
    op.execute("ALTER TABLE study_memos DROP COLUMN IF EXISTS origin_note_id")
