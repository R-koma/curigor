"""create note_embeddings table

Revision ID: a3d8f2c6e1b9
Revises: d6f1b3c8e2a4
Create Date: 2026-10-05 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a3d8f2c6e1b9"
down_revision: str | Sequence[str] | None = "d6f1b3c8e2a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE note_embeddings (
            note_id UUID PRIMARY KEY REFERENCES notes(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            embedding vector(1536) NOT NULL,
            model TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_note_embeddings_user_id ON note_embeddings (user_id)")
    op.execute(
        "CREATE INDEX idx_note_embeddings_embedding ON note_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS note_embeddings")
