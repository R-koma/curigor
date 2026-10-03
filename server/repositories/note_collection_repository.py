from typing import Any
from uuid import UUID

from core.database import DBConnection

_COLUMNS = "id, user_id, name, created_at, updated_at"


async def get_or_create(conn: DBConnection, user_id: str, name: str) -> dict[str, Any]:
    query = f"""--sql
    INSERT INTO note_collections (user_id, name)
    VALUES ($1, $2)
    ON CONFLICT (user_id, name) DO UPDATE SET name = EXCLUDED.name
    RETURNING {_COLUMNS}
    """
    record = await conn.fetchrow(query, user_id, name)
    assert record is not None
    return dict(record)


async def find_by_user_id(conn: DBConnection, user_id: str) -> list[dict[str, Any]]:
    query = """--sql
    SELECT c.id, c.user_id, c.name, c.created_at, c.updated_at, COUNT(n.id) AS note_count
    FROM note_collections c
    LEFT JOIN notes n ON n.collection_id = c.id
    WHERE c.user_id = $1
    GROUP BY c.id
    ORDER BY c.created_at DESC
    """
    records = await conn.fetch(query, user_id)
    return [dict(r) for r in records]


async def find_names_by_user_id(conn: DBConnection, user_id: str) -> list[str]:
    records = await conn.fetch("SELECT name FROM note_collections WHERE user_id = $1 ORDER BY name", user_id)
    return [r["name"] for r in records]


async def find_by_id(conn: DBConnection, collection_id: UUID, user_id: str) -> dict[str, Any] | None:
    query = f"SELECT {_COLUMNS} FROM note_collections WHERE id = $1 AND user_id = $2"
    record = await conn.fetchrow(query, collection_id, user_id)
    return dict(record) if record else None


async def rename(conn: DBConnection, collection_id: UUID, user_id: str, name: str) -> dict[str, Any] | None:
    query = f"""--sql
    UPDATE note_collections
    SET name = $3, updated_at = NOW()
    WHERE id = $1 AND user_id = $2
    RETURNING {_COLUMNS}
    """
    record = await conn.fetchrow(query, collection_id, user_id, name)
    return dict(record) if record else None


async def delete(conn: DBConnection, collection_id: UUID, user_id: str) -> bool:
    result = await conn.execute("DELETE FROM note_collections WHERE id = $1 AND user_id = $2", collection_id, user_id)
    return int(result.split(" ")[1]) > 0
