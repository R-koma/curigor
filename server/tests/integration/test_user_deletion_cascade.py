"""ユーザーを消すと、そのユーザーの行が子のテーブルまで消える（#595）"""

from uuid import UUID, uuid4

import asyncpg
import pytest

from repositories import (
    dialogue_message_repository,
    dialogue_session_repository,
    note_repository,
    side_question_repository,
)

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
        assert await db_conn.fetchval(f"SELECT COUNT(*) FROM {table} WHERE {column} = $1", note_id) == 0  # noqa: S608


async def test_deleting_session_keeps_feedbacks_and_revisions_without_session(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    note_id, session_id = await _insert_note_with_children(db_conn, test_user["id"])

    await db_conn.execute("DELETE FROM dialogue_sessions WHERE id = $1", session_id)

    for table in ("feedbacks", "note_revisions"):
        assert await db_conn.fetchval(f"SELECT dialogue_session_id FROM {table} WHERE note_id = $1", note_id) is None  # noqa: S608


async def test_deleting_user_removes_side_questions(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=db_conn, session_id=session_id, user_id=test_user["id"], session_type="explore", graph_version=2
    )
    answer = await dialogue_message_repository.insert(db_conn, session_id, "assistant", "索引の説明", 1)
    assert answer is not None
    thread = await side_question_repository.create(
        db_conn,
        dialogue_session_id=session_id,
        parent_id=None,
        anchor_message_id=answer["id"],
        anchor_side_message_id=None,
        quote="索引",
        occurrence=0,
        depth=0,
    )
    await side_question_repository.add_message(db_conn, thread["id"], "user", "索引とは？")

    await db_conn.execute('DELETE FROM "user" WHERE id = $1', test_user["id"])

    assert await db_conn.fetchval("SELECT COUNT(*) FROM side_questions") == 0
    assert await db_conn.fetchval("SELECT COUNT(*) FROM side_question_messages") == 0
