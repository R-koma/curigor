from uuid import UUID

from core.database import DBConnection


async def insert(
    conn: DBConnection,
    user_id: str,
    dialogue_session_id: UUID,
    audio_bytes: int,
    model: str,
) -> None:
    query = """--sql
    INSERT INTO transcription_usages (user_id, dialogue_session_id, audio_bytes, model)
    VALUES ($1, $2, $3, $4)
    """
    await conn.execute(query, user_id, str(dialogue_session_id), audio_bytes, model)


async def count_today_by_user(conn: DBConnection, user_id: str, timezone: str) -> int:
    query = """--sql
    SELECT COUNT(*)
    FROM transcription_usages
    WHERE user_id = $1
      AND (created_at AT TIME ZONE $2)::date = (NOW() AT TIME ZONE $2)::date
    """
    count = await conn.fetchval(query, user_id, timezone)
    return int(count)
