"""allow synthesis sessions and store synthesis insights

Revision ID: d9a3e5f7c2b6
Revises: c6e2d8f3b1a4
Create Date: 2026-10-03 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d9a3e5f7c2b6"
down_revision: str | Sequence[str] | None = "c6e2d8f3b1a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE dialogue_sessions DROP CONSTRAINT dialogue_sessions_session_type_check")
    op.execute(
        "ALTER TABLE dialogue_sessions ADD CONSTRAINT dialogue_sessions_session_type_check "
        "CHECK (session_type IN ('learning', 'review', 'synthesis'))"
    )
    op.execute(
        "ALTER TABLE dialogue_sessions "
        "ADD COLUMN collection_id UUID REFERENCES note_collections(id) ON DELETE SET NULL"
    )
    op.execute("""--sql
        CREATE TABLE synthesis_insights (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            collection_id        UUID NOT NULL REFERENCES note_collections(id) ON DELETE CASCADE,
            dialogue_session_id  UUID REFERENCES dialogue_sessions(id) ON DELETE SET NULL,
            connection_title     TEXT NOT NULL,
            content              TEXT NOT NULL,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_synthesis_insights_collection_id ON synthesis_insights(collection_id, created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS synthesis_insights")
    op.execute("ALTER TABLE dialogue_sessions DROP COLUMN IF EXISTS collection_id")
    op.execute("DELETE FROM dialogue_sessions WHERE session_type = 'synthesis'")
    op.execute("ALTER TABLE dialogue_sessions DROP CONSTRAINT dialogue_sessions_session_type_check")
    op.execute(
        "ALTER TABLE dialogue_sessions ADD CONSTRAINT dialogue_sessions_session_type_check "
        "CHECK (session_type IN ('learning', 'review'))"
    )
