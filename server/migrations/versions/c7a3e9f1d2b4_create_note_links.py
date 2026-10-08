"""create note_links

Revision ID: c7a3e9f1d2b4
Revises: b4e7c2a9d1f3
Create Date: 2026-10-08 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c7a3e9f1d2b4"
down_revision: str | Sequence[str] | None = "b4e7c2a9d1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""--sql
        CREATE TABLE note_links (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            note_id_a   UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            note_id_b   UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            similarity  REAL NOT NULL,
            status      TEXT NOT NULL DEFAULT 'suggested' CHECK (status IN ('suggested', 'accepted', 'dismissed')),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CHECK (note_id_a < note_id_b),
            UNIQUE (note_id_a, note_id_b)
        )
    """)
    op.execute("CREATE INDEX idx_note_links_note_id_b ON note_links(note_id_b)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS note_links")
