"""allow_feedback_history_per_note

Revision ID: 3b7e2c9d4f10
Revises: a3d8f2c6e1b9
Create Date: 2026-10-06 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "3b7e2c9d4f10"
down_revision: str | Sequence[str] | None = "a3d8f2c6e1b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE feedbacks DROP CONSTRAINT IF EXISTS feedbacks_note_id_key")
    op.execute("CREATE INDEX feedbacks_note_id_created_at_idx ON feedbacks (note_id, created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS feedbacks_note_id_created_at_idx")
    op.execute("""--sql
        DELETE FROM feedbacks f
        USING feedbacks f2
        WHERE f.note_id = f2.note_id
          AND (f.created_at < f2.created_at
               OR (f.created_at = f2.created_at AND f.id < f2.id))
    """)
    op.execute("ALTER TABLE feedbacks ADD CONSTRAINT feedbacks_note_id_key UNIQUE (note_id)")
