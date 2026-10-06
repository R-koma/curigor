from typing import Any
from uuid import UUID

from core.database import DBConnection


async def find_by_note_id(conn: DBConnection, note_id: UUID, user_id: str) -> list[dict[str, Any]]:
    query = """--sql
    SELECT f.id, f.note_id, f.dialogue_session_id, f.understanding_level, f.strength, f.improvements,
           f.improvement_items, f.created_at,
           s.session_type
    FROM feedbacks f
    JOIN notes n ON n.id = f.note_id
    LEFT JOIN dialogue_sessions s ON s.id = f.dialogue_session_id
    WHERE f.note_id = $1 AND n.user_id = $2
    ORDER BY f.created_at ASC
  """

    records = await conn.fetch(query, note_id, user_id)
    return [dict(r) for r in records]


async def insert(
    conn: DBConnection,
    note_id: UUID,
    dialogue_session_id: UUID,
    understanding_level: str,
    strength: str,
    improvements: str,
    improvement_items: str | None = None,
) -> dict[str, Any]:
    query = """--sql
    INSERT INTO feedbacks (id, note_id, dialogue_session_id, understanding_level, strength, improvements,
                           improvement_items)
    VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6::jsonb)
    RETURNING *
    """
    record = await conn.fetchrow(
        query, note_id, dialogue_session_id, understanding_level, strength, improvements, improvement_items
    )
    assert record is not None
    return dict(record)
