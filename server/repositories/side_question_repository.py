from typing import Any
from uuid import UUID

from core.database import DBConnection

_THREAD_COLUMN_NAMES = (
    "id",
    "dialogue_session_id",
    "parent_id",
    "anchor_message_id",
    "anchor_side_message_id",
    "quote",
    "occurrence",
    "depth",
    "created_at",
)
_THREAD_COLUMNS = ", ".join(_THREAD_COLUMN_NAMES)
_Q_THREAD_COLUMNS = ", ".join(f"q.{name}" for name in _THREAD_COLUMN_NAMES)


async def create(
    conn: DBConnection,
    *,
    dialogue_session_id: UUID,
    parent_id: UUID | None,
    anchor_message_id: UUID | None,
    anchor_side_message_id: UUID | None,
    quote: str,
    occurrence: int,
    depth: int,
) -> dict[str, Any]:
    record = await conn.fetchrow(
        f"""--sql
        INSERT INTO side_questions
            (dialogue_session_id, parent_id, anchor_message_id, anchor_side_message_id, quote, occurrence, depth)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING {_THREAD_COLUMNS}
        """,  # noqa: S608
        dialogue_session_id,
        parent_id,
        anchor_message_id,
        anchor_side_message_id,
        quote,
        occurrence,
        depth,
    )
    assert record is not None
    return dict(record)


async def find_owned(conn: DBConnection, side_question_id: UUID, user_id: str) -> dict[str, Any] | None:
    record = await conn.fetchrow(
        f"""--sql
        SELECT {_Q_THREAD_COLUMNS}
        FROM side_questions q
        JOIN dialogue_sessions s ON s.id = q.dialogue_session_id
        WHERE q.id = $1 AND s.user_id = $2
        """,  # noqa: S608
        side_question_id,
        user_id,
    )
    return dict(record) if record is not None else None


async def add_message(
    conn: DBConnection,
    side_question_id: UUID,
    role: str,
    content: str,
    *,
    message_id: UUID | None = None,
) -> dict[str, Any]:
    async with conn.transaction():
        await conn.execute("SELECT 1 FROM side_questions WHERE id = $1 FOR UPDATE", side_question_id)
        record = await conn.fetchrow(
            """--sql
            INSERT INTO side_question_messages (id, side_question_id, role, content, message_order)
            VALUES (
                COALESCE($1, gen_random_uuid()), $2, $3, $4,
                (SELECT COALESCE(MAX(message_order), 0) + 1 FROM side_question_messages WHERE side_question_id = $2)
            )
            RETURNING id, side_question_id, role, content, message_order, created_at
            """,
            message_id,
            side_question_id,
            role,
            content,
        )
    assert record is not None
    return dict(record)


async def delete_message(conn: DBConnection, message_id: UUID) -> None:
    await conn.execute("DELETE FROM side_question_messages WHERE id = $1", message_id)


async def delete_if_empty(conn: DBConnection, side_question_id: UUID) -> None:
    await conn.execute(
        """--sql
        DELETE FROM side_questions q
        WHERE q.id = $1
          AND NOT EXISTS (SELECT 1 FROM side_question_messages m WHERE m.side_question_id = q.id)
        """,
        side_question_id,
    )


async def find_threads(conn: DBConnection, dialogue_session_id: UUID) -> list[dict[str, Any]]:
    records = await conn.fetch(
        f"""--sql
        SELECT {_Q_THREAD_COLUMNS}, m.id AS message_id, m.role, m.content
        FROM side_questions q
        JOIN side_question_messages m ON m.side_question_id = q.id
        WHERE q.dialogue_session_id = $1
        ORDER BY q.created_at, q.id, m.message_order
        """,  # noqa: S608
        dialogue_session_id,
    )
    threads: dict[UUID, dict[str, Any]] = {}
    for r in records:
        thread = threads.get(r["id"])
        if thread is None:
            thread = {key: r[key] for key in _THREAD_COLUMN_NAMES}
            thread["messages"] = []
            threads[r["id"]] = thread
        thread["messages"].append({"id": r["message_id"], "role": r["role"], "content": r["content"]})
    return list(threads.values())


async def has_threads(conn: DBConnection, dialogue_session_id: UUID) -> bool:
    return bool(
        await conn.fetchval(
            """--sql
            SELECT EXISTS (
                SELECT 1 FROM side_questions q
                JOIN side_question_messages m ON m.side_question_id = q.id
                WHERE q.dialogue_session_id = $1
            )
            """,
            dialogue_session_id,
        )
    )


async def find_side_message_owner(conn: DBConnection, side_message_id: UUID) -> dict[str, Any] | None:
    record = await conn.fetchrow(
        f"""--sql
        SELECT {_Q_THREAD_COLUMNS}, m.role, m.content
        FROM side_question_messages m
        JOIN side_questions q ON q.id = m.side_question_id
        WHERE m.id = $1
        """,  # noqa: S608
        side_message_id,
    )
    return dict(record) if record is not None else None
