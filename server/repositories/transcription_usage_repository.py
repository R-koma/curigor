from uuid import UUID

from core.database import DBConnection


async def insert(
    conn: DBConnection,
    user_id: str,
    dialogue_session_id: UUID | None,
    audio_bytes: int,
    audio_seconds: float,
    model: str,
) -> UUID:
    query = """--sql
    INSERT INTO transcription_usages (user_id, dialogue_session_id, audio_bytes, audio_seconds, model)
    VALUES ($1, $2, $3, $4, $5)
    RETURNING id
    """
    session_id = str(dialogue_session_id) if dialogue_session_id is not None else None
    usage_id: UUID = await conn.fetchval(query, user_id, session_id, audio_bytes, audio_seconds, model)
    return usage_id


async def sum_seconds_today_by_user(conn: DBConnection, user_id: str, timezone: str) -> float:
    query = """--sql
    SELECT COALESCE(SUM(audio_seconds), 0)
    FROM transcription_usages
    WHERE user_id = $1
      AND (created_at AT TIME ZONE $2)::date = (NOW() AT TIME ZONE $2)::date
    """
    total = await conn.fetchval(query, user_id, timezone)
    return float(total)


async def reserve(
    conn: DBConnection,
    user_id: str,
    dialogue_session_id: UUID | None,
    audio_bytes: int,
    audio_seconds: float,
    model: str,
    timezone: str,
    limit: float,
) -> UUID | None:
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(hashtext('transcription_usages:' || $1))", user_id)
        if await sum_seconds_today_by_user(conn, user_id, timezone) >= limit:
            return None
        return await insert(conn, user_id, dialogue_session_id, audio_bytes, audio_seconds, model)


async def cancel(conn: DBConnection, usage_id: UUID) -> None:
    await conn.execute("DELETE FROM transcription_usages WHERE id = $1", usage_id)
