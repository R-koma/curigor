from uuid import UUID

from core.database import DBConnection


async def insert(conn: DBConnection, user_id: str, dialogue_session_id: UUID, characters: int, model: str) -> None:
    query = """--sql
    INSERT INTO transcript_format_usages (user_id, dialogue_session_id, characters, model)
    VALUES ($1, $2, $3, $4)
    """
    await conn.execute(query, user_id, str(dialogue_session_id), characters, model)


async def sum_today_by_user(conn: DBConnection, user_id: str, timezone: str) -> int:
    query = """--sql
    SELECT COALESCE(SUM(characters), 0)
    FROM transcript_format_usages
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
) -> bool:
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(hashtext('transcript_format_usages:' || $1))", user_id)
        if await sum_today_by_user(conn, user_id, timezone) >= limit:
            return False
        await insert(conn, user_id, dialogue_session_id, characters, model)
    return True
