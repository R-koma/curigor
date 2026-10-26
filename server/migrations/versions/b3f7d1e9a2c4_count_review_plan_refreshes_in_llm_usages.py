"""count review plan refreshes in llm_usages

Revision ID: b3f7d1e9a2c4
Revises: a8e3c5b7d912
Create Date: 2026-10-27 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b3f7d1e9a2c4"
down_revision: str | Sequence[str] | None = "a8e3c5b7d912"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE llm_usages DROP CONSTRAINT llm_usages_operation_check")
    op.execute("""--sql
        ALTER TABLE llm_usages ADD CONSTRAINT llm_usages_operation_check
        CHECK (operation IN ('session_start', 'turn', 'synthesis', 'review_plan'))
    """)


def downgrade() -> None:
    op.execute("DELETE FROM llm_usages WHERE operation = 'review_plan'")
    op.execute("ALTER TABLE llm_usages DROP CONSTRAINT llm_usages_operation_check")
    op.execute("""--sql
        ALTER TABLE llm_usages ADD CONSTRAINT llm_usages_operation_check
        CHECK (operation IN ('session_start', 'turn', 'synthesis'))
    """)
