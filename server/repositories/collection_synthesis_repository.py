import json
from typing import Any
from uuid import UUID

import asyncpg

from core.database import DBConnection

_JSON_COLUMNS = ("connections", "contradictions", "gaps", "source_notes")
_COLUMNS = "s.collection_id, s.content, s.connections, s.contradictions, s.gaps, s.source_notes, s.generated_at"


def _decode(record: asyncpg.Record) -> dict[str, Any]:
    row = dict(record)
    for column in _JSON_COLUMNS:
        if isinstance(row[column], str):
            row[column] = json.loads(row[column])
    return row


async def upsert(
    conn: DBConnection,
    *,
    collection_id: UUID,
    content: str,
    connections: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
    gaps: list[str],
    source_notes: list[dict[str, str]],
) -> dict[str, Any]:
    query = """--sql
    INSERT INTO collection_syntheses AS s (collection_id, content, connections, contradictions, gaps, source_notes)
    VALUES ($1, $2, $3::jsonb, $4::jsonb, $5::jsonb, $6::jsonb)
    ON CONFLICT (collection_id) DO UPDATE SET
        content = EXCLUDED.content,
        connections = EXCLUDED.connections,
        contradictions = EXCLUDED.contradictions,
        gaps = EXCLUDED.gaps,
        source_notes = EXCLUDED.source_notes,
        generated_at = NOW()
    RETURNING s.collection_id, s.content, s.connections, s.contradictions, s.gaps, s.source_notes, s.generated_at
    """
    record = await conn.fetchrow(
        query,
        collection_id,
        content,
        json.dumps(connections, ensure_ascii=False),
        json.dumps(contradictions, ensure_ascii=False),
        json.dumps(gaps, ensure_ascii=False),
        json.dumps(source_notes),
    )
    assert record is not None
    return _decode(record)


async def find_by_collection_id(conn: DBConnection, collection_id: UUID, user_id: str) -> dict[str, Any] | None:
    query = f"""--sql
    SELECT {_COLUMNS}
    FROM collection_syntheses s
    JOIN note_collections c ON c.id = s.collection_id
    WHERE s.collection_id = $1 AND c.user_id = $2
    """
    record = await conn.fetchrow(query, collection_id, user_id)
    return _decode(record) if record else None
