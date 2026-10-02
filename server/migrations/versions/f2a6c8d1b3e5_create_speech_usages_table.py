"""create speech_usages table

Revision ID: f2a6c8d1b3e5
Revises: e9c3a7f1b5d2
Create Date: 2026-10-03 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f2a6c8d1b3e5"
down_revision: str | Sequence[str] | None = "e9c3a7f1b5d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""--sql
        CREATE TABLE speech_usages (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id             TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            dialogue_session_id UUID NOT NULL REFERENCES dialogue_sessions(id) ON DELETE CASCADE,
            characters          INTEGER NOT NULL,
            model               TEXT NOT NULL,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_speech_usages_user_created ON speech_usages(user_id, created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_speech_usages_user_created")
    op.execute("DROP TABLE IF EXISTS speech_usages")
