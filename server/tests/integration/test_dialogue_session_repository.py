from uuid import UUID, uuid4

import asyncpg
import pytest

from repositories import dialogue_message_repository, dialogue_session_repository, note_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_create_persists_graph_version(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = uuid4()

    created = await dialogue_session_repository.create(
        conn=db_conn,
        session_id=session_id,
        user_id=test_user["id"],
        session_type="learning",
        graph_version=2,
    )

    assert created["graph_version"] == 2


async def test_find_by_id_returns_graph_version(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = uuid4()
    note_id = uuid4()
    await note_repository.insert(db_conn, note_id, test_user["id"], topic="t", content="c", summary="s")
    await dialogue_session_repository.create(
        conn=db_conn,
        session_id=session_id,
        user_id=test_user["id"],
        session_type="review",
        graph_version=2,
        note_id=note_id,
    )

    found = await dialogue_session_repository.find_by_id(db_conn, session_id, test_user["id"])

    assert found is not None
    assert found["graph_version"] == 2


async def test_create_defaults_note_id_to_null(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    created = await dialogue_session_repository.create(
        conn=db_conn,
        session_id=uuid4(),
        user_id=test_user["id"],
        session_type="learning",
        graph_version=2,
    )

    assert created["note_id"] is None


async def test_create_persists_note_id_for_review(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    note_id = uuid4()
    await note_repository.insert(db_conn, note_id, test_user["id"], topic="t", content="c", summary="s")

    created = await dialogue_session_repository.create(
        conn=db_conn,
        session_id=uuid4(),
        user_id=test_user["id"],
        session_type="review",
        graph_version=2,
        note_id=note_id,
    )

    assert created["note_id"] == note_id


async def _learning_session_with_first_message(db_conn: asyncpg.Connection, user_id: str) -> UUID:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=db_conn, session_id=session_id, user_id=user_id, session_type="learning", graph_version=2
    )
    await dialogue_message_repository.insert(db_conn, session_id, "user", "仕事でReactのフックを使うので", 1)
    return session_id


async def test_topic_falls_back_to_first_user_message(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])

    found = await dialogue_session_repository.find_by_id(db_conn, session_id, test_user["id"])
    resumable = await dialogue_session_repository.find_resumable_by_user(db_conn, test_user["id"])

    assert found is not None and found["topic"] == "仕事でReactのフックを使うので"
    assert resumable is not None and resumable["topic"] == "仕事でReactのフックを使うので"


async def test_update_topic_overrides_first_message(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])

    await dialogue_session_repository.update_topic(db_conn, session_id, "React Hooks")

    found = await dialogue_session_repository.find_by_id(db_conn, session_id, test_user["id"])
    resumable = await dialogue_session_repository.find_resumable_by_user(db_conn, test_user["id"])
    assert found is not None and found["topic"] == "React Hooks"
    assert resumable is not None and resumable["topic"] == "React Hooks"


async def test_disconnect_does_not_overwrite_a_finished_session(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])
    await dialogue_session_repository.update_status(db_conn, session_id, "completed")

    await dialogue_session_repository.update_status(db_conn, session_id, "disconnect")

    found = await dialogue_session_repository.find_by_id(db_conn, session_id, test_user["id"])
    assert found is not None and found["status"] == "completed"
    assert await dialogue_session_repository.find_resumable_by_user(db_conn, test_user["id"]) is None


async def test_learning_session_with_a_note_is_not_resumable(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])
    note_id = uuid4()
    await note_repository.insert(db_conn, note_id, test_user["id"], topic="t", content="c", summary="s")
    await dialogue_session_repository.update_note_id(db_conn, session_id, note_id)
    await dialogue_session_repository.update_status(db_conn, session_id, "in_progress")

    assert await dialogue_session_repository.find_resumable_by_user(db_conn, test_user["id"]) is None


async def test_synthesis_sessions_are_never_resumable(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    await dialogue_session_repository.create(
        db_conn,
        session_id=uuid4(),
        user_id=test_user["id"],
        session_type="synthesis",
        graph_version=4,
        topic="Linuxのしくみ",
    )

    assert await dialogue_session_repository.find_resumable_by_user(db_conn, test_user["id"]) is None
