from typing import Literal
from uuid import UUID

from core.database import DBConnection

LlmOperation = Literal["session_start", "turn", "synthesis"]


async def count_today(conn: DBConnection, user_id: str, operation: LlmOperation, timezone: str) -> int:
    query = """--sql
    SELECT COUNT(*)
    FROM llm_usages
    WHERE user_id = $1
      AND operation = $2
      AND (created_at AT TIME ZONE $3)::date = (NOW() AT TIME ZONE $3)::date
    """
    total = await conn.fetchval(query, user_id, operation, timezone)
    return int(total)


async def reserve(conn: DBConnection, user_id: str, operation: LlmOperation, timezone: str, limit: int) -> UUID | None:
    async with conn.transaction():
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtext('llm_usages:' || $1::text || ':' || $2::text))", operation, user_id
        )
        if await count_today(conn, user_id, operation, timezone) >= limit:
            return None
        usage_id: UUID = await conn.fetchval(
            "INSERT INTO llm_usages (user_id, operation) VALUES ($1, $2) RETURNING id", user_id, operation
        )
        return usage_id


async def cancel(conn: DBConnection, usage_id: UUID) -> None:
    await conn.execute("DELETE FROM llm_usages WHERE id = $1", usage_id)
