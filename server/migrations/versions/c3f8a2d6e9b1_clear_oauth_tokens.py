"""clear stored OAuth tokens

Revision ID: c3f8a2d6e9b1
Revises: b5e1c7a9d3f2
Create Date: 2026-10-15 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c3f8a2d6e9b1"
down_revision: str | Sequence[str] | None = "b5e1c7a9d3f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.account') IS NOT NULL THEN
                UPDATE account
                SET "accessToken" = NULL, "refreshToken" = NULL, "idToken" = NULL,
                    "accessTokenExpiresAt" = NULL, "refreshTokenExpiresAt" = NULL;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    pass
