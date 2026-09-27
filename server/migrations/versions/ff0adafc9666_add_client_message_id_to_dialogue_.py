"""add client_message_id to dialogue_messages

Revision ID: ff0adafc9666
Revises: 4439695e5a34
Create Date: 2026-09-27 18:57:44.685627

"""

from collections.abc import Sequence

from alembic import op

revision: str = "ff0adafc9666"
down_revision: str | Sequence[str] | None = "4439695e5a34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE dialogue_messages ADD COLUMN client_message_id UUID")
    op.execute("""--sql
        CREATE UNIQUE INDEX idx_dialogue_messages_client_message_id
        ON dialogue_messages(dialogue_session_id, client_message_id)
        WHERE client_message_id IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_dialogue_messages_client_message_id")
    op.execute("ALTER TABLE dialogue_messages DROP COLUMN IF EXISTS client_message_id")
