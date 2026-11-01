"""create reflection tables and llm operations

Revision ID: d2a6f8b4c1e7
Revises: c5d9e1f3a7b2
Create Date: 2026-11-01 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d2a6f8b4c1e7"
down_revision: str | Sequence[str] | None = "c5d9e1f3a7b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""--sql
        CREATE TABLE reflection_views (
            user_id   TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            day       DATE NOT NULL,
            viewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, day)
        )
    """)
    op.execute("""--sql
        CREATE TABLE reflection_generations (
            user_id      TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            period       TEXT NOT NULL CHECK (period IN ('day', 'week')),
            start_date   DATE NOT NULL,
            kind         TEXT NOT NULL CHECK (kind IN ('script', 'quiz')),
            content_hash TEXT NOT NULL,
            payload      JSONB NOT NULL,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, period, start_date, kind)
        )
    """)
    op.execute("ALTER TABLE llm_usages DROP CONSTRAINT llm_usages_operation_check")
    op.execute("""--sql
        ALTER TABLE llm_usages ADD CONSTRAINT llm_usages_operation_check
        CHECK (operation IN (
            'session_start', 'turn', 'synthesis', 'review_plan', 'reflection_script', 'reflection_quiz'
        ))
    """)


def downgrade() -> None:
    op.execute("DELETE FROM llm_usages WHERE operation IN ('reflection_script', 'reflection_quiz')")
    op.execute("ALTER TABLE llm_usages DROP CONSTRAINT llm_usages_operation_check")
    op.execute("""--sql
        ALTER TABLE llm_usages ADD CONSTRAINT llm_usages_operation_check
        CHECK (operation IN ('session_start', 'turn', 'synthesis', 'review_plan'))
    """)
    op.execute("DROP TABLE IF EXISTS reflection_generations")
    op.execute("DROP TABLE IF EXISTS reflection_views")
