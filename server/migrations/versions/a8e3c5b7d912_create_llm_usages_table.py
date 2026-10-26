"""create llm_usages table

Revision ID: a8e3c5b7d912
Revises: d4b7e2a9c6f1
Create Date: 2026-10-26 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a8e3c5b7d912"
down_revision: str | Sequence[str] | None = "d4b7e2a9c6f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""--sql
        CREATE TABLE llm_usages (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id    TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            operation  TEXT NOT NULL CHECK (operation IN ('session_start', 'turn', 'synthesis')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_llm_usages_user_operation_created ON llm_usages(user_id, operation, created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_llm_usages_user_operation_created")
    op.execute("DROP TABLE IF EXISTS llm_usages")
