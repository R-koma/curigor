from datetime import timedelta
from typing import Any, Literal
from uuid import UUID

from core.database import DBConnection

_TOPIC_SQL = """COALESCE(
        s.topic,
        (
            SELECT content
            FROM dialogue_messages
            WHERE dialogue_session_id = s.id AND role = 'user'
            ORDER BY message_order ASC
            LIMIT 1
        )
    ) AS topic"""


async def create(
    conn: DBConnection,
    session_id: UUID,
    user_id: str,
    session_type: str,
    graph_version: int,
    note_id: UUID | None = None,
    collection_id: UUID | None = None,
    topic: str | None = None,
    is_trial: bool = False,
    study_memo_id: UUID | None = None,
    connection_id: UUID | None = None,
) -> dict[str, Any]:
    query = """--sql
    INSERT INTO dialogue_sessions (
        id, user_id, session_type, status, graph_version, note_id, collection_id, topic, is_trial, study_memo_id,
        connection_id
    )
    VALUES ($1, $2, $3, 'in_progress', $4, $5, $6, $7, $8, $9, $10)
    RETURNING *
    """
    record = await conn.fetchrow(
        query,
        str(session_id),
        user_id,
        session_type,
        graph_version,
        str(note_id) if note_id else None,
        collection_id,
        topic,
        is_trial,
        study_memo_id,
        connection_id,
    )
    assert record is not None
    return dict(record)


async def update_topic(conn: DBConnection, session_id: UUID, topic: str) -> None:
    query = """--sql
    UPDATE dialogue_sessions SET topic = $2 WHERE id = $1
    """
    await conn.execute(query, str(session_id), topic)


async def find_transcription_keywords(
    conn: DBConnection, session_id: UUID, user_id: str
) -> tuple[list[str] | None, str | None]:
    query = """--sql
    SELECT transcription_keywords, transcription_keywords_source
    FROM dialogue_sessions
    WHERE id = $1 AND user_id = $2
    """
    record = await conn.fetchrow(query, str(session_id), user_id)
    if record is None:
        return None, None
    return record["transcription_keywords"], record["transcription_keywords_source"]


async def update_transcription_keywords(
    conn: DBConnection, session_id: UUID, keywords: list[str], source: str
) -> None:
    query = """--sql
    UPDATE dialogue_sessions SET transcription_keywords = $2, transcription_keywords_source = $3 WHERE id = $1
    """
    await conn.execute(query, str(session_id), keywords, source)


async def update_note_id(
    conn: DBConnection,
    session_id: UUID,
    note_id: UUID,
) -> dict[str, Any] | None:
    query = """--sql
    UPDATE dialogue_sessions
    SET note_id = $2, status = 'completed', ended_at = NOW()
    WHERE id = $1
    RETURNING *
    """
    record = await conn.fetchrow(query, str(session_id), str(note_id))
    return dict(record) if record else None


async def update_status(
    conn: DBConnection,
    session_id: UUID,
    status: str,
) -> dict[str, Any] | None:
    if status == "disconnect":
        query = """--sql
        UPDATE dialogue_sessions
        SET status = $2, ended_at = NOW()
        WHERE id = $1 AND status = 'in_progress'
        RETURNING *
        """
    elif status == "generate_note":
        query = """--sql
        UPDATE dialogue_sessions
        SET status = $2, generation_started_at = NOW()
        WHERE id = $1
        RETURNING *
        """
    else:
        query = """--sql
        UPDATE dialogue_sessions
        SET status = $2
        WHERE id = $1
        RETURNING *
        """
    record = await conn.fetchrow(query, str(session_id), status)
    return dict(record) if record else None


async def claim_connection(conn: DBConnection, session_id: UUID, user_id: str, connection_id: UUID) -> bool:
    query = """--sql
    UPDATE dialogue_sessions
    SET connection_id = $3, status = 'in_progress'
    WHERE id = $1
      AND user_id = $2
      AND status IN ('in_progress', 'disconnect')
    RETURNING id
    """
    return await conn.fetchval(query, str(session_id), user_id, connection_id) is not None


async def is_held_by(conn: DBConnection, session_id: UUID, connection_id: UUID) -> bool:
    query = """--sql
    SELECT EXISTS (
        SELECT 1 FROM dialogue_sessions
        WHERE id = $1 AND connection_id = $2 AND status = 'in_progress'
    )
    """
    return bool(await conn.fetchval(query, str(session_id), connection_id))


async def release_connection(
    conn: DBConnection, session_id: UUID, connection_id: UUID, status: Literal["disconnect", "failed"]
) -> None:
    query = """--sql
    UPDATE dialogue_sessions
    SET status = $3, ended_at = CASE WHEN $3 = 'disconnect' THEN NOW() ELSE ended_at END
    WHERE id = $1 AND connection_id = $2 AND status = 'in_progress'
    """
    await conn.execute(query, str(session_id), connection_id, status)


async def begin_turn(conn: DBConnection, session_id: UUID, connection_id: UUID) -> None:
    query = """--sql
    UPDATE dialogue_sessions SET turn_started_at = NOW() WHERE id = $1 AND connection_id = $2
    """
    await conn.execute(query, str(session_id), connection_id)


async def finish_turn(conn: DBConnection, session_id: UUID, connection_id: UUID) -> bool:
    query = """--sql
    UPDATE dialogue_sessions
    SET turn_started_at = NULL
    WHERE id = $1 AND connection_id = $2 AND status = 'in_progress'
    RETURNING id
    """
    return await conn.fetchval(query, str(session_id), connection_id) is not None


async def clear_turn(conn: DBConnection, session_id: UUID) -> None:
    query = """--sql
    UPDATE dialogue_sessions SET turn_started_at = NULL WHERE id = $1
    """
    await conn.execute(query, str(session_id))


async def has_turn_in_flight(conn: DBConnection, session_id: UUID, stale_after: timedelta) -> bool:
    query = """--sql
    SELECT EXISTS (
        SELECT 1 FROM dialogue_sessions
        WHERE id = $1 AND turn_started_at > NOW() - $2::interval
    )
    """
    return bool(await conn.fetchval(query, str(session_id), stale_after))


async def find_by_id(
    conn: DBConnection,
    session_id: UUID,
    user_id: str,
) -> dict[str, Any] | None:
    query = f"""--sql
    SELECT s.id, s.user_id, s.session_type, s.status, s.note_id, s.started_at, s.ended_at, s.graph_version, s.is_trial,
        s.study_memo_id,
        {_TOPIC_SQL}
    FROM dialogue_sessions s
    WHERE s.id = $1 AND s.user_id = $2
    """  # noqa: S608
    record = await conn.fetchrow(query, str(session_id), user_id)
    return dict(record) if record else None


async def find_resumable_by_user(
    conn: DBConnection,
    user_id: str,
) -> dict[str, Any] | None:
    query = f"""--sql
    SELECT
        s.id,
        s.user_id,
        s.session_type,
        s.status,
        s.note_id,
        s.started_at,
        s.ended_at,
        {_TOPIC_SQL}
    FROM dialogue_sessions s
    WHERE s.user_id = $1
      AND s.status IN ('in_progress', 'disconnect')
      AND s.session_type <> 'synthesis'
      AND NOT (s.session_type = 'learning' AND s.note_id IS NOT NULL)
      AND COALESCE(s.ended_at, s.started_at) > NOW() - INTERVAL '30 days'
    ORDER BY COALESCE(s.ended_at, s.started_at) DESC
    LIMIT 1
    """  # noqa: S608
    record = await conn.fetchrow(query, user_id)
    return dict(record) if record else None


async def abandon_by_id(
    conn: DBConnection,
    session_id: UUID,
    user_id: str,
) -> dict[str, Any] | None:
    query = """--sql
    UPDATE dialogue_sessions
    SET status = 'abandoned', ended_at = NOW()
    WHERE id = $1
      AND user_id = $2
      AND status IN ('in_progress', 'disconnect')
    RETURNING *
    """
    record = await conn.fetchrow(query, str(session_id), user_id)
    return dict(record) if record else None


async def abandon_active_by_user(
    conn: DBConnection,
    user_id: str,
) -> int:
    query = """--sql
    UPDATE dialogue_sessions
    SET status = 'abandoned', ended_at = NOW()
    WHERE user_id = $1
      AND status IN ('in_progress', 'disconnect')
      AND session_type <> 'synthesis'
    """
    result = await conn.execute(query, user_id)
    return int(result.split(" ")[1])


async def reset_stuck_generations(conn: DBConnection, stale_after: timedelta) -> list[UUID]:
    """開始から stale_after 以上たった生成中のセッションを failed に戻し、その ID を返す。

    generation_started_at が NULL の行は、列を足す前に生成中のまま残ったものなので常に戻す。
    """
    query = """--sql
    UPDATE dialogue_sessions
    SET status = 'failed'
    WHERE status = 'generate_note'
      AND (generation_started_at IS NULL OR generation_started_at < NOW() - $1::interval)
    RETURNING id
    """
    records = await conn.fetch(query, stale_after)
    return [r["id"] for r in records]


async def find_ids_by_user(conn: DBConnection, user_id: str) -> list[UUID]:
    records = await conn.fetch("SELECT id FROM dialogue_sessions WHERE user_id = $1", user_id)
    return [r["id"] for r in records]


async def find_existing_ids(conn: DBConnection, session_ids: list[UUID]) -> set[UUID]:
    records = await conn.fetch("SELECT id FROM dialogue_sessions WHERE id = ANY($1::uuid[])", session_ids)
    return {r["id"] for r in records}


async def find_orphaned_checkpoint_thread_ids(conn: DBConnection) -> list[str]:
    records = await conn.fetch(
        """--sql
        SELECT thread_id FROM checkpoints
        UNION SELECT thread_id FROM checkpoint_blobs
        UNION SELECT thread_id FROM checkpoint_writes
        EXCEPT SELECT id::text FROM dialogue_sessions
        """
    )
    return [r["thread_id"] for r in records]


async def find_ids_by_note(conn: DBConnection, note_id: UUID, user_id: str) -> list[UUID]:
    query = "SELECT id FROM dialogue_sessions WHERE note_id = $1 AND user_id = $2"
    records = await conn.fetch(query, note_id, user_id)
    return [r["id"] for r in records]


async def find_ids_by_collection(conn: DBConnection, collection_id: UUID, user_id: str) -> list[UUID]:
    query = "SELECT id FROM dialogue_sessions WHERE collection_id = $1 AND user_id = $2"
    records = await conn.fetch(query, collection_id, user_id)
    return [r["id"] for r in records]


async def delete_by_ids(conn: DBConnection, session_ids: list[UUID], user_id: str) -> None:
    query = "DELETE FROM dialogue_sessions WHERE id = ANY($1::uuid[]) AND user_id = $2"
    await conn.execute(query, session_ids, user_id)
