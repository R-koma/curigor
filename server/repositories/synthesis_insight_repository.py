from collections.abc import Sequence
from typing import Any
from uuid import UUID

from core.database import DBConnection


async def insert_many(
    conn: DBConnection,
    *,
    collection_id: UUID,
    dialogue_session_id: UUID | str,
    insights: Sequence[tuple[str, str]],
) -> None:
    await conn.executemany(
        """--sql
        INSERT INTO synthesis_insights (collection_id, dialogue_session_id, connection_title, content, created_at)
        VALUES ($1, $2, $3, $4, clock_timestamp())
        """,
        [(collection_id, str(dialogue_session_id), title, content) for title, content in insights],
    )


async def find_by_collection_id(conn: DBConnection, collection_id: UUID, user_id: str) -> list[dict[str, Any]]:
    query = """--sql
    SELECT i.id, i.connection_title, i.content, i.created_at
    FROM synthesis_insights i
    JOIN note_collections c ON c.id = i.collection_id
    WHERE i.collection_id = $1 AND c.user_id = $2
    ORDER BY i.created_at ASC, i.id ASC
    """
    records = await conn.fetch(query, collection_id, user_id)
    return [dict(r) for r in records]
