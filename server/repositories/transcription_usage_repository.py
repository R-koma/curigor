from uuid import UUID

from core.database import DBConnection


async def insert(
    conn: DBConnection,
    user_id: str,
    dialogue_session_id: UUID | None,
    audio_bytes: int,
    audio_seconds: float,
    model: str,
) -> None:
    query = """--sql
    INSERT INTO transcription_usages (user_id, dialogue_session_id, audio_bytes, audio_seconds, model)
    VALUES ($1, $2, $3, $4, $5)
    """
    session_id = str(dialogue_session_id) if dialogue_session_id is not None else None
    await conn.execute(query, user_id, session_id, audio_bytes, audio_seconds, model)


async def sum_seconds_today_by_user(conn: DBConnection, user_id: str, timezone: str) -> float:
    query = """--sql
    SELECT COALESCE(SUM(audio_seconds), 0)
    FROM transcription_usages
    WHERE user_id = $1
      AND (created_at AT TIME ZONE $2)::date = (NOW() AT TIME ZONE $2)::date
    """
    total = await conn.fetchval(query, user_id, timezone)
    return float(total)
