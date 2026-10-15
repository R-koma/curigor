"""keep speech_usages when the dialogue session is deleted

Revision ID: b8e4d2a6c1f9
Revises: 6b09e59b760f
Create Date: 2026-10-16 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b8e4d2a6c1f9"
down_revision: str | Sequence[str] | None = "6b09e59b760f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE speech_usages DROP CONSTRAINT speech_usages_dialogue_session_id_fkey")
    op.execute("ALTER TABLE speech_usages ALTER COLUMN dialogue_session_id DROP NOT NULL")
    op.execute(
        "ALTER TABLE speech_usages ADD CONSTRAINT speech_usages_dialogue_session_id_fkey "
        "FOREIGN KEY (dialogue_session_id) REFERENCES dialogue_sessions(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute("DELETE FROM speech_usages WHERE dialogue_session_id IS NULL")
    op.execute("ALTER TABLE speech_usages DROP CONSTRAINT speech_usages_dialogue_session_id_fkey")
    op.execute("ALTER TABLE speech_usages ALTER COLUMN dialogue_session_id SET NOT NULL")
    op.execute(
        "ALTER TABLE speech_usages ADD CONSTRAINT speech_usages_dialogue_session_id_fkey "
        "FOREIGN KEY (dialogue_session_id) REFERENCES dialogue_sessions(id) ON DELETE CASCADE"
    )
