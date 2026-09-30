from typing import Any
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
) -> dict[str, Any]:
    query = """--sql
    INSERT INTO dialogue_sessions (id, user_id, session_type, status, graph_version, note_id)
    VALUES ($1, $2, $3, 'in_progress', $4, $5)
    RETURNING *
    """
    record = await conn.fetchrow(
        query, str(session_id), user_id, session_type, graph_version, str(note_id) if note_id else None
    )
    assert record is not None
    return dict(record)


async def update_topic(conn: DBConnection, session_id: UUID, topic: str) -> None:
    query = """--sql
    UPDATE dialogue_sessions SET topic = $2 WHERE id = $1
    """
    await conn.execute(query, str(session_id), topic)


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


async def find_by_id(
    conn: DBConnection,
    session_id: UUID,
    user_id: str,
) -> dict[str, Any] | None:
    query = f"""--sql
    SELECT s.id, s.user_id, s.session_type, s.status, s.note_id, s.started_at, s.ended_at, s.graph_version,
        {_TOPIC_SQL}
    FROM dialogue_sessions s
    WHERE s.id = $1 AND s.user_id = $2
    """
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
      AND COALESCE(s.ended_at, s.started_at) > NOW() - INTERVAL '30 days'
    ORDER BY COALESCE(s.ended_at, s.started_at) DESC
    LIMIT 1
    """
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
    """
    result = await conn.execute(query, user_id)
    return int(result.split(" ")[1])


async def reset_stuck_generations(conn: DBConnection) -> int:
    query = """--sql
    UPDATE dialogue_sessions
    SET status = 'failed'
    WHERE status = 'generate_note'
    """
    result = await conn.execute(query)
    return int(result.split(" ")[1])
