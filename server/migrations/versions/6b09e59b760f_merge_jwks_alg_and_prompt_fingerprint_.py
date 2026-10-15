"""merge jwks alg and prompt_fingerprint heads

Revision ID: 6b09e59b760f
Revises: 9a4f5edd6682, c3f8a1d5e7b9
Create Date: 2026-10-15 23:12:31.028804

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "6b09e59b760f"
down_revision: str | Sequence[str] | None = ("9a4f5edd6682", "c3f8a1d5e7b9")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
