from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from repositories import (
    dialogue_message_image_repository,
    dialogue_message_repository,
    dialogue_session_repository,
    feedback_repository,
    note_collection_repository,
    note_repository,
    note_revision_repository,
    speech_usage_repository,
)
from services.note_deletion import delete_collection, delete_note
from storage.local import LocalObjectStorage
from tests.integration.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.asyncio(loop_scope="session")

_OTHER_USER_ID = "other-user-659"


@pytest_asyncio.fixture(loop_scope="session")
async def checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    async with AsyncPostgresSaver.from_conn_string(TEST_DATABASE_URL) as saver:
        await saver.setup()
        yield saver


@pytest_asyncio.fixture(loop_scope="session")
async def other_user(test_pool: asyncpg.Pool) -> str:
    async with test_pool.acquire() as conn:
        await conn.execute(
            """--sql
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES ($1, 'Other', 'other-659@example.com', true)
            ON CONFLICT (id) DO NOTHING
            """,
            _OTHER_USER_ID,
        )
    return _OTHER_USER_ID


async def _note(conn: asyncpg.Connection, user_id: str) -> UUID:
    note_id = uuid4()
    await note_repository.insert(conn, note_id=note_id, user_id=user_id, topic="二分探索", content="c", summary="s")
    return note_id


async def _session(
    conn: asyncpg.Connection,
    saver: AsyncPostgresSaver,
    storage: LocalObjectStorage,
    user_id: str,
    session_type: str = "learning",
    note_id: UUID | None = None,
    collection_id: UUID | None = None,
) -> tuple[UUID, str]:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn, session_id, user_id, session_type, graph_version=1, note_id=note_id, collection_id=collection_id
    )
    message = await dialogue_message_repository.insert(conn, session_id, "user", "hi", 0)
    assert message is not None
    key = f"dialogue_images/{session_id}/{message['id']}/0.png"
    await storage.put(key, b"png", "image/png")
    await dialogue_message_image_repository.insert_many(conn, message["id"], [(key, "image/png")])
    await saver.aput({"configurable": {"thread_id": str(session_id), "checkpoint_ns": ""}}, empty_checkpoint(), {}, {})
    return session_id, key


async def _has_checkpoint(saver: AsyncPostgresSaver, session_id: UUID) -> bool:
    return await saver.aget_tuple({"configurable": {"thread_id": str(session_id)}}) is not None


async def _session_exists(conn: asyncpg.Connection, session_id: UUID) -> bool:
    return bool(await conn.fetchval("SELECT EXISTS (SELECT 1 FROM dialogue_sessions WHERE id = $1)", session_id))


async def test_deleting_a_note_removes_its_sessions_checkpoints_and_images(
    db_conn: asyncpg.Connection, test_user: dict[str, str], checkpointer: AsyncPostgresSaver, tmp_path: Path
) -> None:
    storage = LocalObjectStorage(tmp_path)
    note_id = await _note(db_conn, test_user["id"])
    learning, learning_key = await _session(db_conn, checkpointer, storage, test_user["id"], note_id=note_id)
    review, review_key = await _session(db_conn, checkpointer, storage, test_user["id"], "review", note_id=note_id)
    await feedback_repository.insert(db_conn, note_id, review, "high", "強み", "改善点")
    await note_revision_repository.insert(db_conn, note_id, review, "前の本文")
    other_note_id = await _note(db_conn, test_user["id"])
    kept, kept_key = await _session(db_conn, checkpointer, storage, test_user["id"], note_id=other_note_id)

    assert await delete_note(db_conn, checkpointer, storage, note_id, test_user["id"])

    for session_id, key in ((learning, learning_key), (review, review_key)):
        assert not await _session_exists(db_conn, session_id)
        assert not await _has_checkpoint(checkpointer, session_id)
        assert not (tmp_path / key).exists()
    assert await _session_exists(db_conn, kept)
    assert await _has_checkpoint(checkpointer, kept)
    assert (tmp_path / kept_key).exists()


async def test_deleting_a_note_keeps_the_speech_usage_of_its_sessions(
    db_conn: asyncpg.Connection, test_user: dict[str, str], checkpointer: AsyncPostgresSaver, tmp_path: Path
) -> None:
    storage = LocalObjectStorage(tmp_path)
    note_id = await _note(db_conn, test_user["id"])
    session_id, _ = await _session(db_conn, checkpointer, storage, test_user["id"], note_id=note_id)
    await speech_usage_repository.insert(db_conn, test_user["id"], session_id, 1234, "tts")
    before = await speech_usage_repository.sum_today_by_user(db_conn, test_user["id"], "UTC")

    await delete_note(db_conn, checkpointer, storage, note_id, test_user["id"])

    assert await speech_usage_repository.sum_today_by_user(db_conn, test_user["id"], "UTC") == before


async def test_deleting_another_users_note_changes_nothing(
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    other_user: str,
    checkpointer: AsyncPostgresSaver,
    tmp_path: Path,
) -> None:
    storage = LocalObjectStorage(tmp_path)
    note_id = await _note(db_conn, other_user)
    session_id, key = await _session(db_conn, checkpointer, storage, other_user, note_id=note_id)

    assert not await delete_note(db_conn, checkpointer, storage, note_id, test_user["id"])

    assert await note_repository.find_by_id(db_conn, note_id, other_user) is not None
    assert await _session_exists(db_conn, session_id)
    assert await _has_checkpoint(checkpointer, session_id)
    assert (tmp_path / key).exists()


async def test_deleting_a_collection_removes_its_synthesis_sessions_but_keeps_notes_and_their_sessions(
    db_conn: asyncpg.Connection, test_user: dict[str, str], checkpointer: AsyncPostgresSaver, tmp_path: Path
) -> None:
    storage = LocalObjectStorage(tmp_path)
    collection = await note_collection_repository.get_or_create(db_conn, test_user["id"], f"まとめ-{uuid4()}")
    note_id = await _note(db_conn, test_user["id"])
    await note_repository.set_collection(db_conn, note_id, test_user["id"], collection["id"])
    learning, learning_key = await _session(db_conn, checkpointer, storage, test_user["id"], note_id=note_id)
    synthesis, synthesis_key = await _session(
        db_conn, checkpointer, storage, test_user["id"], "synthesis", collection_id=collection["id"]
    )

    assert await delete_collection(db_conn, checkpointer, storage, collection["id"], test_user["id"])

    assert not await _session_exists(db_conn, synthesis)
    assert not await _has_checkpoint(checkpointer, synthesis)
    assert not (tmp_path / synthesis_key).exists()
    assert await note_repository.find_by_id(db_conn, note_id, test_user["id"]) is not None
    assert await _session_exists(db_conn, learning)
    assert await _has_checkpoint(checkpointer, learning)
    assert (tmp_path / learning_key).exists()


async def test_deleting_another_users_collection_changes_nothing(
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    other_user: str,
    checkpointer: AsyncPostgresSaver,
    tmp_path: Path,
) -> None:
    storage = LocalObjectStorage(tmp_path)
    collection = await note_collection_repository.get_or_create(db_conn, other_user, f"まとめ-{uuid4()}")
    session_id, key = await _session(
        db_conn, checkpointer, storage, other_user, "synthesis", collection_id=collection["id"]
    )

    assert not await delete_collection(db_conn, checkpointer, storage, collection["id"], test_user["id"])

    assert await note_collection_repository.find_by_id(db_conn, collection["id"], other_user) is not None
    assert await _session_exists(db_conn, session_id)
    assert await _has_checkpoint(checkpointer, session_id)
    assert (tmp_path / key).exists()
