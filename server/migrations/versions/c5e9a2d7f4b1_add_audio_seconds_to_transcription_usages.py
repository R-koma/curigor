"""add audio_seconds to transcription_usages

Revision ID: c5e9a2d7f4b1
Revises: e7a2c4b9d1f6
Create Date: 2026-10-05 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c5e9a2d7f4b1"
down_revision: str | Sequence[str] | None = "e7a2c4b9d1f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE transcription_usages ADD COLUMN audio_seconds DOUBLE PRECISION")
    # 既存行は 64kbps 固定の webm / mp4
    op.execute("UPDATE transcription_usages SET audio_seconds = audio_bytes / 8000.0")
    op.execute("ALTER TABLE transcription_usages ALTER COLUMN audio_seconds SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE transcription_usages DROP COLUMN IF EXISTS audio_seconds")
