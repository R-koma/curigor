"""create transcription_usages table

Revision ID: d4e8b2c7a1f3
Revises: a3f1c8d2e9b7
Create Date: 2026-10-02 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d4e8b2c7a1f3"
down_revision: str | Sequence[str] | None = "a3f1c8d2e9b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""--sql
        CREATE TABLE transcription_usages (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id             TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            dialogue_session_id UUID REFERENCES dialogue_sessions(id) ON DELETE SET NULL,
            audio_bytes         INTEGER NOT NULL,
            model               TEXT NOT NULL,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_transcription_usages_user_created ON transcription_usages(user_id, created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_transcription_usages_user_created")
    op.execute("DROP TABLE IF EXISTS transcription_usages")
