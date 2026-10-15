"""cascade note deletion to review schedules and detach feedbacks and revisions from deleted sessions

Revision ID: b5e1c7a9d3f2
Revises: a8d2f4c6e1b3
Create Date: 2026-10-15 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b5e1c7a9d3f2"
down_revision: str | Sequence[str] | None = "a8d2f4c6e1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rebuild(table: str, column: str, references: str, on_delete: str | None) -> None:
    constraint = f"{table}_{column}_fkey"
    action = f" ON DELETE {on_delete}" if on_delete else ""
    op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {constraint}")
    op.execute(
        f"ALTER TABLE {table} ADD CONSTRAINT {constraint} FOREIGN KEY ({column}) REFERENCES {references}(id){action}"
    )


def upgrade() -> None:
    _rebuild("review_schedules", "note_id", "notes", "CASCADE")
    _rebuild("feedbacks", "dialogue_session_id", "dialogue_sessions", "SET NULL")
    _rebuild("note_revisions", "dialogue_session_id", "dialogue_sessions", "SET NULL")


def downgrade() -> None:
    _rebuild("review_schedules", "note_id", "notes", None)
    _rebuild("feedbacks", "dialogue_session_id", "dialogue_sessions", None)
    _rebuild("note_revisions", "dialogue_session_id", "dialogue_sessions", None)
