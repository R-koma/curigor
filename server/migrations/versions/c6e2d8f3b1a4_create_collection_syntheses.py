"""create collection_syntheses

Revision ID: c6e2d8f3b1a4
Revises: b4f1c7e2a9d3
Create Date: 2026-10-03 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c6e2d8f3b1a4"
down_revision: str | Sequence[str] | None = "b4f1c7e2a9d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""--sql
        CREATE TABLE collection_syntheses (
            collection_id   UUID PRIMARY KEY REFERENCES note_collections(id) ON DELETE CASCADE,
            content         TEXT NOT NULL,
            connections     JSONB NOT NULL,
            contradictions  JSONB NOT NULL,
            gaps            JSONB NOT NULL,
            source_notes    JSONB NOT NULL,
            generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS collection_syntheses")
