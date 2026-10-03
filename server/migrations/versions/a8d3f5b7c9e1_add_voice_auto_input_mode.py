"""allow voice_auto in dialogue_messages.input_mode

Revision ID: a8d3f5b7c9e1
Revises: f2a6c8d1b3e5
Create Date: 2026-10-03 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a8d3f5b7c9e1"
down_revision: str | Sequence[str] | None = "f2a6c8d1b3e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE dialogue_messages DROP CONSTRAINT dialogue_messages_input_mode_check")
    op.execute(
        "ALTER TABLE dialogue_messages ADD CONSTRAINT dialogue_messages_input_mode_check "
        "CHECK (input_mode IN ('text', 'voice', 'voice_auto'))"
    )


def downgrade() -> None:
    op.execute("UPDATE dialogue_messages SET input_mode = 'voice' WHERE input_mode = 'voice_auto'")
    op.execute("ALTER TABLE dialogue_messages DROP CONSTRAINT dialogue_messages_input_mode_check")
    op.execute(
        "ALTER TABLE dialogue_messages ADD CONSTRAINT dialogue_messages_input_mode_check "
        "CHECK (input_mode IN ('text', 'voice'))"
    )
