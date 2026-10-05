"""add stt_method and stt_latency_ms to dialogue_messages

Revision ID: d6f1b3c8e2a4
Revises: c5e9a2d7f4b1
Create Date: 2026-10-05 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d6f1b3c8e2a4"
down_revision: str | Sequence[str] | None = "c5e9a2d7f4b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE dialogue_messages ADD COLUMN stt_method TEXT CHECK (stt_method IN ('segmented', 'streaming'))"
    )
    op.execute("ALTER TABLE dialogue_messages ADD COLUMN stt_latency_ms INTEGER CHECK (stt_latency_ms >= 0)")


def downgrade() -> None:
    op.execute("ALTER TABLE dialogue_messages DROP COLUMN IF EXISTS stt_latency_ms")
    op.execute("ALTER TABLE dialogue_messages DROP COLUMN IF EXISTS stt_method")
