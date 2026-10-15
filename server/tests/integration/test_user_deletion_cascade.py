"""ユーザーを消すと、そのユーザーの行が子のテーブルまで消える（#595）"""

from uuid import UUID, uuid4

import asyncpg
import pytest

from repositories import note_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _insert_note_with_children(conn: asyncpg.Connection, user_id: str) -> tuple[UUID, UUID]:
    note_id = uuid4()
    session_id = uuid4()
    await note_repository.insert(conn, note_id=note_id, user_id=user_id, topic="T", content="C", summary="S")
    await conn.execute(
        """--sql
        INSERT INTO dialogue_sessions (id, user_id, session_type, status, note_id)
        VALUES ($1, $2, 'review', 'completed', $3)
        """,
        session_id,
        user_id,
        note_id,
    )
    await conn.execute(
        """--sql
        INSERT INTO feedbacks (id, note_id, dialogue_session_id, understanding_level, strength, improvements)
        VALUES ($1, $2, $3, 'high', 'Good', 'None')
        """,
        uuid4(),
        note_id,
        session_id,
    )
    await conn.execute(
        "INSERT INTO note_revisions (note_id, dialogue_session_id, content) VALUES ($1, $2, 'addendum')",
        note_id,
        session_id,
    )
    await conn.execute(
        "INSERT INTO review_schedules (id, note_id, next_review_at) VALUES ($1, $2, NOW() + INTERVAL '1 day')",
        uuid4(),
        note_id,
    )
    return note_id, session_id


async def test_deleting_user_removes_review_schedules_feedbacks_and_revisions(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    note_id, _ = await _insert_note_with_children(db_conn, test_user["id"])

    await db_conn.execute('DELETE FROM "user" WHERE id = $1', test_user["id"])

    for table in ("notes", "feedbacks", "note_revisions", "review_schedules"):
        column = "id" if table == "notes" else "note_id"
        assert await db_conn.fetchval(f"SELECT COUNT(*) FROM {table} WHERE {column} = $1", note_id) == 0


async def test_deleting_session_keeps_feedbacks_and_revisions_without_session(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    note_id, session_id = await _insert_note_with_children(db_conn, test_user["id"])

    await db_conn.execute("DELETE FROM dialogue_sessions WHERE id = $1", session_id)

    for table in ("feedbacks", "note_revisions"):
        assert await db_conn.fetchval(f"SELECT dialogue_session_id FROM {table} WHERE note_id = $1", note_id) is None
