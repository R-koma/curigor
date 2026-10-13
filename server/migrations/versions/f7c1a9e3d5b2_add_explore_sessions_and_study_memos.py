"""allow explore sessions and store study memos

Revision ID: f7c1a9e3d5b2
Revises: e3b9d7a1c4f6
Create Date: 2026-10-13 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f7c1a9e3d5b2"
down_revision: str | Sequence[str] | None = "e3b9d7a1c4f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE dialogue_sessions DROP CONSTRAINT dialogue_sessions_session_type_check")
    op.execute(
        "ALTER TABLE dialogue_sessions ADD CONSTRAINT dialogue_sessions_session_type_check "
        "CHECK (session_type IN ('learning', 'review', 'synthesis', 'explore'))"
    )
    op.execute("""--sql
        CREATE TABLE study_memos (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id              TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            dialogue_session_id  UUID NOT NULL UNIQUE REFERENCES dialogue_sessions(id) ON DELETE CASCADE,
            topic                TEXT NOT NULL,
            source               TEXT NOT NULL DEFAULT '',
            overview             JSONB NOT NULL,
            glossary             JSONB NOT NULL,
            questions            JSONB NOT NULL,
            depth_map            JSONB NOT NULL,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_study_memos_user_id ON study_memos(user_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS study_memos")
    op.execute("DELETE FROM dialogue_sessions WHERE session_type = 'explore'")
    op.execute("ALTER TABLE dialogue_sessions DROP CONSTRAINT dialogue_sessions_session_type_check")
    op.execute(
        "ALTER TABLE dialogue_sessions ADD CONSTRAINT dialogue_sessions_session_type_check "
        "CHECK (session_type IN ('learning', 'review', 'synthesis'))"
    )
