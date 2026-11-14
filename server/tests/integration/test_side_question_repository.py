from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from repositories import dialogue_message_repository, dialogue_session_repository, side_question_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _explore_session(conn: asyncpg.Connection, user_id: str) -> tuple[UUID, UUID]:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=conn, session_id=session_id, user_id=user_id, session_type="explore", graph_version=2
    )
    await dialogue_message_repository.insert(conn, session_id, "user", "インデックスとは", 1)
    answer = await dialogue_message_repository.insert(conn, session_id, "assistant", "索引の構造を説明します", 2)
    assert answer is not None
    return session_id, answer["id"]


async def _thread_with_answer(
    conn: asyncpg.Connection,
    session_id: UUID,
    *,
    anchor_message_id: UUID | None = None,
    parent: dict[str, Any] | None = None,
    anchor_side_message_id: UUID | None = None,
    quote: str = "索引",
) -> tuple[dict[str, Any], dict[str, Any]]:
    thread = await side_question_repository.create(
        conn,
        dialogue_session_id=session_id,
        parent_id=parent["id"] if parent else None,
        anchor_message_id=anchor_message_id,
        anchor_side_message_id=anchor_side_message_id,
        quote=quote,
        occurrence=0,
        depth=(int(parent["depth"]) + 1) if parent else 0,
    )
    await side_question_repository.add_message(conn, thread["id"], "user", f"{quote}とは？")
    answer = await side_question_repository.add_message(conn, thread["id"], "assistant", f"{quote}の説明")
    return thread, answer


async def test_create_and_find_threads_returns_messages_in_order(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id, anchor_id = await _explore_session(db_conn, test_user["id"])
    thread, _ = await _thread_with_answer(db_conn, session_id, anchor_message_id=anchor_id)
    await side_question_repository.add_message(db_conn, thread["id"], "user", "もう少し")

    threads = await side_question_repository.find_threads(db_conn, session_id)

    assert len(threads) == 1
    assert threads[0]["id"] == thread["id"]
    assert threads[0]["anchor_message_id"] == anchor_id
    assert threads[0]["quote"] == "索引"
    assert [m["content"] for m in threads[0]["messages"]] == ["索引とは？", "索引の説明", "もう少し"]
    assert [m["role"] for m in threads[0]["messages"]] == ["user", "assistant", "user"]


async def test_find_threads_excludes_threads_without_messages(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id, anchor_id = await _explore_session(db_conn, test_user["id"])
    empty = await side_question_repository.create(
        db_conn,
        dialogue_session_id=session_id,
        parent_id=None,
        anchor_message_id=anchor_id,
        anchor_side_message_id=None,
        quote="構造",
        occurrence=0,
        depth=0,
    )

    assert await side_question_repository.find_threads(db_conn, session_id) == []

    await side_question_repository.delete_if_empty(db_conn, empty["id"])
    assert await db_conn.fetchval("SELECT COUNT(*) FROM side_questions") == 0


async def test_delete_if_empty_keeps_thread_with_messages(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id, anchor_id = await _explore_session(db_conn, test_user["id"])
    thread, answer = await _thread_with_answer(db_conn, session_id, anchor_message_id=anchor_id)

    await side_question_repository.delete_message(db_conn, answer["id"])
    await side_question_repository.delete_if_empty(db_conn, thread["id"])

    threads = await side_question_repository.find_threads(db_conn, session_id)
    assert [m["content"] for m in threads[0]["messages"]] == ["索引とは？"]


async def test_find_owned_returns_none_for_other_user(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id, anchor_id = await _explore_session(db_conn, test_user["id"])
    thread, _ = await _thread_with_answer(db_conn, session_id, anchor_message_id=anchor_id)

    owned = await side_question_repository.find_owned(db_conn, thread["id"], test_user["id"])
    other = await side_question_repository.find_owned(db_conn, thread["id"], "someone-else")

    assert owned is not None
    assert owned["dialogue_session_id"] == session_id
    assert other is None


async def test_find_side_message_owner_returns_thread_of_answer(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id, anchor_id = await _explore_session(db_conn, test_user["id"])
    thread, answer = await _thread_with_answer(db_conn, session_id, anchor_message_id=anchor_id)

    owner = await side_question_repository.find_side_message_owner(db_conn, answer["id"])

    assert owner is not None
    assert owner["id"] == thread["id"]
    assert owner["depth"] == 0
    assert owner["role"] == "assistant"
    assert await side_question_repository.find_side_message_owner(db_conn, uuid4()) is None


async def test_deleting_anchor_dialogue_message_cascades_to_thread_and_children(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id, anchor_id = await _explore_session(db_conn, test_user["id"])
    parent, parent_answer = await _thread_with_answer(db_conn, session_id, anchor_message_id=anchor_id)
    await _thread_with_answer(
        db_conn,
        session_id,
        parent=parent,
        anchor_side_message_id=parent_answer["id"],
        quote="説明",
    )

    await dialogue_message_repository.delete_last_n(db_conn, session_id, 1)

    assert await db_conn.fetchval("SELECT COUNT(*) FROM side_questions") == 0
    assert await db_conn.fetchval("SELECT COUNT(*) FROM side_question_messages") == 0


async def test_deleting_session_cascades(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id, anchor_id = await _explore_session(db_conn, test_user["id"])
    await _thread_with_answer(db_conn, session_id, anchor_message_id=anchor_id)

    await dialogue_session_repository.delete_by_ids(db_conn, [session_id], test_user["id"])

    assert await db_conn.fetchval("SELECT COUNT(*) FROM side_questions") == 0
    assert await db_conn.fetchval("SELECT COUNT(*) FROM side_question_messages") == 0


async def test_depth_over_3_is_rejected(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id, anchor_id = await _explore_session(db_conn, test_user["id"])
    parent, answer = await _thread_with_answer(db_conn, session_id, anchor_message_id=anchor_id)

    with pytest.raises(asyncpg.CheckViolationError):
        await side_question_repository.create(
            db_conn,
            dialogue_session_id=session_id,
            parent_id=parent["id"],
            anchor_message_id=None,
            anchor_side_message_id=answer["id"],
            quote="索引",
            occurrence=0,
            depth=4,
        )


async def test_both_anchors_or_neither_is_rejected(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id, anchor_id = await _explore_session(db_conn, test_user["id"])
    parent, answer = await _thread_with_answer(db_conn, session_id, anchor_message_id=anchor_id)

    with pytest.raises(asyncpg.CheckViolationError):
        await side_question_repository.create(
            db_conn,
            dialogue_session_id=session_id,
            parent_id=parent["id"],
            anchor_message_id=anchor_id,
            anchor_side_message_id=answer["id"],
            quote="索引",
            occurrence=0,
            depth=1,
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await side_question_repository.create(
            db_conn,
            dialogue_session_id=session_id,
            parent_id=None,
            anchor_message_id=None,
            anchor_side_message_id=None,
            quote="索引",
            occurrence=0,
            depth=0,
        )
