"""create side questions tables

Revision ID: 84cac66387cc
Revises: d2a6f8b4c1e7
Create Date: 2026-11-14 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "84cac66387cc"
down_revision: str | Sequence[str] | None = "d2a6f8b4c1e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""--sql
        CREATE TABLE side_questions (
            id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            dialogue_session_id    UUID NOT NULL REFERENCES dialogue_sessions(id) ON DELETE CASCADE,
            parent_id              UUID REFERENCES side_questions(id) ON DELETE CASCADE,
            anchor_message_id      UUID REFERENCES dialogue_messages(id) ON DELETE CASCADE,
            anchor_side_message_id UUID,
            quote                  TEXT NOT NULL,
            occurrence             INTEGER NOT NULL CHECK (occurrence >= 0),
            depth                  INTEGER NOT NULL CHECK (depth BETWEEN 0 AND 3),
            created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT side_questions_one_anchor_check
                CHECK ((anchor_message_id IS NULL) <> (anchor_side_message_id IS NULL)),
            CONSTRAINT side_questions_parent_anchor_check
                CHECK ((parent_id IS NULL) = (anchor_message_id IS NOT NULL))
        )
    """)
    op.execute("CREATE INDEX idx_side_questions_dialogue_session_id ON side_questions (dialogue_session_id)")
    op.execute("""--sql
        CREATE TABLE side_question_messages (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            side_question_id UUID NOT NULL REFERENCES side_questions(id) ON DELETE CASCADE,
            role             TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content          TEXT NOT NULL,
            message_order    INTEGER NOT NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (side_question_id, message_order)
        )
    """)
    op.execute("""--sql
        ALTER TABLE side_questions ADD CONSTRAINT side_questions_anchor_side_message_id_fkey
        FOREIGN KEY (anchor_side_message_id) REFERENCES side_question_messages(id) ON DELETE CASCADE
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE side_questions DROP CONSTRAINT IF EXISTS side_questions_anchor_side_message_id_fkey")
    op.execute("DROP TABLE IF EXISTS side_question_messages")
    op.execute("DROP TABLE IF EXISTS side_questions")
