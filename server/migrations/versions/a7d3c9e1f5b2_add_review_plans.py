"""add review_plans and feedbacks.review_results

Revision ID: a7d3c9e1f5b2
Revises: c5e8a1d3f7b2
Create Date: 2026-10-18 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a7d3c9e1f5b2"
down_revision: str | Sequence[str] | None = "c5e8a1d3f7b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE review_plans (
            note_id UUID PRIMARY KEY REFERENCES notes(id) ON DELETE CASCADE,
            points JSONB NOT NULL,
            note_content_hash TEXT NOT NULL,
            prompt_fingerprint TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("ALTER TABLE feedbacks ADD COLUMN review_results JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE feedbacks DROP COLUMN review_results")
    op.execute("DROP TABLE review_plans")
