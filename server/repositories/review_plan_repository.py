import json
from typing import Any
from uuid import UUID

from core.database import DBConnection


async def find_by_note_id(conn: DBConnection, note_id: UUID, user_id: str) -> dict[str, Any] | None:
    query = """--sql
    SELECT p.note_id, p.points, p.note_content_hash, p.prompt_fingerprint, p.created_at, p.updated_at
    FROM review_plans p
    JOIN notes n ON n.id = p.note_id
    WHERE p.note_id = $1 AND n.user_id = $2
    """
    record = await conn.fetchrow(query, note_id, user_id)
    if record is None:
        return None
    row = dict(record)
    row["points"] = json.loads(row["points"])
    return row


async def upsert(
    conn: DBConnection,
    note_id: UUID,
    points: str,
    note_content_hash: str,
    prompt_fingerprint: str,
) -> None:
    query = """--sql
    INSERT INTO review_plans (note_id, points, note_content_hash, prompt_fingerprint)
    VALUES ($1, $2::jsonb, $3, $4)
    ON CONFLICT (note_id) DO UPDATE
    SET points = EXCLUDED.points,
        note_content_hash = EXCLUDED.note_content_hash,
        prompt_fingerprint = EXCLUDED.prompt_fingerprint,
        updated_at = now()
    """
    await conn.execute(query, note_id, points, note_content_hash, prompt_fingerprint)
