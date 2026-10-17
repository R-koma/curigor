"""create user_consents table

Revision ID: d4b9e2c7a1f6
Revises: a6d2f8c4e1b3
Create Date: 2026-10-17 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d4b9e2c7a1f6"
down_revision: str | Sequence[str] | None = "a6d2f8c4e1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""--sql
        CREATE TABLE user_consents (
            user_id       TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            terms_version INTEGER NOT NULL,
            consented_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, terms_version)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_consents")
