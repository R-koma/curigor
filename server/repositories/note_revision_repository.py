from typing import Any
from uuid import UUID

from core.database import DBConnection


async def insert(
    conn: DBConnection,
    note_id: UUID,
    dialogue_session_id: UUID,
    content: str,
    prompt_fingerprint: str | None = None,
) -> dict[str, Any]:
    query = """--sql
    INSERT INTO note_revisions (note_id, dialogue_session_id, content, prompt_fingerprint)
    VALUES ($1, $2, $3, $4)
    RETURNING id, note_id, dialogue_session_id, content, created_at
    """
    record = await conn.fetchrow(query, note_id, dialogue_session_id, content, prompt_fingerprint)
    assert record is not None
    return dict(record)


async def find_by_note_id(conn: DBConnection, note_id: UUID, user_id: str) -> list[dict[str, Any]]:
    query = """--sql
    SELECT r.id, r.note_id, r.dialogue_session_id, r.content, r.created_at
    FROM note_revisions r
    JOIN notes n ON n.id = r.note_id
    WHERE r.note_id = $1 AND n.user_id = $2
    ORDER BY r.created_at ASC
    """
    records = await conn.fetch(query, note_id, user_id)
    return [dict(r) for r in records]
