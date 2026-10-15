"""add alg and crv to jwks

Revision ID: 9a4f5edd6682
Revises: c3f8a2d6e9b1
Create Date: 2026-10-15 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "9a4f5edd6682"
down_revision: str | Sequence[str] | None = "c3f8a2d6e9b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # better-auth 1.7 の jwt プラグインは鍵の作成時に alg・crv を書き込む
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.jwks') IS NOT NULL THEN
                ALTER TABLE jwks ADD COLUMN IF NOT EXISTS "alg" text, ADD COLUMN IF NOT EXISTS "crv" text;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.jwks') IS NOT NULL THEN
                ALTER TABLE jwks DROP COLUMN IF EXISTS "alg", DROP COLUMN IF EXISTS "crv";
            END IF;
        END $$;
        """
    )
