"""create user_hint_dismissals table

Revision ID: c7e1a9d3f5b2
Revises: a4c8e2f6b1d3
Create Date: 2026-10-09 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c7e1a9d3f5b2"
down_revision: str | Sequence[str] | None = "a4c8e2f6b1d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_HINT_IDS = (
    "dashboard",
    "learn_start",
    "intake_card",
    "chat_input",
    "dialogue",
    "end_session",
    "note_detail",
)


def upgrade() -> None:
    op.execute("""--sql
        CREATE TABLE user_hint_dismissals (
            user_id      TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            hint_id      TEXT NOT NULL,
            dismissed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, hint_id)
        )
    """)
    hint_ids = ", ".join(f"('{hint_id}')" for hint_id in _HINT_IDS)
    op.execute(f"""--sql
        INSERT INTO user_hint_dismissals (user_id, hint_id)
        SELECT users.user_id, hints.hint_id
        FROM (SELECT DISTINCT user_id FROM notes) AS users
        CROSS JOIN (VALUES {hint_ids}) AS hints(hint_id)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_hint_dismissals")
