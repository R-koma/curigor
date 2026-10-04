"""create note_collections and link notes to them

Revision ID: b4f1c7e2a9d3
Revises: a8d3f5b7c9e1
Create Date: 2026-10-03 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b4f1c7e2a9d3"
down_revision: str | Sequence[str] | None = "a8d3f5b7c9e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""--sql
        CREATE TABLE note_collections (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (user_id, name)
        )
    """)
    op.execute("ALTER TABLE notes ADD COLUMN collection_id UUID REFERENCES note_collections(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE notes ADD COLUMN suggested_collection TEXT")
    op.execute("CREATE INDEX idx_notes_collection_id ON notes(collection_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_notes_collection_id")
    op.execute("ALTER TABLE notes DROP COLUMN IF EXISTS suggested_collection")
    op.execute("ALTER TABLE notes DROP COLUMN IF EXISTS collection_id")
    op.execute("DROP TABLE IF EXISTS note_collections")
