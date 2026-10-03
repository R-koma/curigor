from uuid import UUID

from core.database import DBConnection


async def insert(conn: DBConnection, user_id: str, dialogue_session_id: UUID, characters: int, model: str) -> None:
    query = """--sql
    INSERT INTO speech_usages (user_id, dialogue_session_id, characters, model)
    VALUES ($1, $2, $3, $4)
    """
    await conn.execute(query, user_id, str(dialogue_session_id), characters, model)


async def sum_today_by_user(conn: DBConnection, user_id: str, timezone: str) -> int:
    query = """--sql
    SELECT COALESCE(SUM(characters), 0)
    FROM speech_usages
    WHERE user_id = $1
      AND (created_at AT TIME ZONE $2)::date = (NOW() AT TIME ZONE $2)::date
    """
    total = await conn.fetchval(query, user_id, timezone)
    return int(total)
