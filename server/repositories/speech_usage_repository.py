from uuid import UUID

from core.database import DBConnection


async def insert(conn: DBConnection, user_id: str, dialogue_session_id: UUID, characters: int, model: str) -> UUID:
    query = """--sql
    INSERT INTO speech_usages (user_id, dialogue_session_id, characters, model)
    VALUES ($1, $2, $3, $4)
    RETURNING id
    """
    usage_id: UUID = await conn.fetchval(query, user_id, str(dialogue_session_id), characters, model)
    return usage_id


async def sum_today_by_user(conn: DBConnection, user_id: str, timezone: str) -> int:
    query = """--sql
    SELECT COALESCE(SUM(characters), 0)
    FROM speech_usages
    WHERE user_id = $1
      AND (created_at AT TIME ZONE $2)::date = (NOW() AT TIME ZONE $2)::date
    """
    total = await conn.fetchval(query, user_id, timezone)
    return int(total)


async def reserve(
    conn: DBConnection,
    user_id: str,
    dialogue_session_id: UUID,
    characters: int,
    model: str,
    timezone: str,
    limit: int,
) -> UUID | None:
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(hashtext('speech_usages:' || $1))", user_id)
        if await sum_today_by_user(conn, user_id, timezone) >= limit:
            return None
        return await insert(conn, user_id, dialogue_session_id, characters, model)


async def cancel(conn: DBConnection, usage_id: UUID) -> None:
    await conn.execute("DELETE FROM speech_usages WHERE id = $1", usage_id)
