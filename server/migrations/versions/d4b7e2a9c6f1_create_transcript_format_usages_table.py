"""create transcript_format_usages table

Revision ID: d4b7e2a9c6f1
Revises: a7d3c9e1f5b2
Create Date: 2026-10-23 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d4b7e2a9c6f1"
down_revision: str | Sequence[str] | None = "a7d3c9e1f5b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""--sql
        CREATE TABLE transcript_format_usages (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id             TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            dialogue_session_id UUID REFERENCES dialogue_sessions(id) ON DELETE SET NULL,
            characters          INTEGER NOT NULL,
            model               TEXT NOT NULL,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX idx_transcript_format_usages_user_created ON transcript_format_usages(user_id, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_transcript_format_usages_user_created")
    op.execute("DROP TABLE IF EXISTS transcript_format_usages")
