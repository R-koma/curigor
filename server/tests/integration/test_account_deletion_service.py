from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from repositories import dialogue_message_image_repository, dialogue_message_repository, dialogue_session_repository
from services.account_deletion import purge_user_data
from storage.local import LocalObjectStorage
from tests.integration.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.asyncio(loop_scope="session")

_OTHER_USER_ID = "other-user-598"


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
            VALUES ($1, 'Other', 'other-598@example.com', true)
            ON CONFLICT (id) DO NOTHING
            """,
            _OTHER_USER_ID,
        )
    return _OTHER_USER_ID


async def _session_with_image(
    conn: asyncpg.Connection, saver: AsyncPostgresSaver, storage: LocalObjectStorage, user_id: str
) -> tuple[UUID, str]:
    session_id = uuid4()
    await dialogue_session_repository.create(conn, session_id, user_id, "learning", graph_version=1)
    message = await dialogue_message_repository.insert(conn, session_id, "user", "hi", 0)
    assert message is not None
    key = f"dialogue_images/{session_id}/{message['id']}/0.png"
    await storage.put(key, b"png", "image/png")
    await dialogue_message_image_repository.insert_many(conn, message["id"], [(key, "image/png")])
    await saver.aput({"configurable": {"thread_id": str(session_id), "checkpoint_ns": ""}}, empty_checkpoint(), {}, {})
    return session_id, key


async def _has_checkpoint(saver: AsyncPostgresSaver, session_id: UUID) -> bool:
    return await saver.aget_tuple({"configurable": {"thread_id": str(session_id)}}) is not None


async def test_purge_removes_only_the_users_checkpoints_and_images(
    test_pool: asyncpg.Pool,
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    other_user: str,
    checkpointer: AsyncPostgresSaver,
    tmp_path: Path,
) -> None:
    storage = LocalObjectStorage(tmp_path)
    mine, my_key = await _session_with_image(db_conn, checkpointer, storage, test_user["id"])
    theirs, their_key = await _session_with_image(db_conn, checkpointer, storage, other_user)

    await purge_user_data(test_pool, checkpointer, storage, test_user["id"])

    assert not await _has_checkpoint(checkpointer, mine)
    assert not (tmp_path / my_key).exists()
    assert await _has_checkpoint(checkpointer, theirs)
    assert (tmp_path / their_key).exists()


async def test_purge_removes_images_whose_message_was_deleted(
    test_pool: asyncpg.Pool,
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    checkpointer: AsyncPostgresSaver,
    tmp_path: Path,
) -> None:
    storage = LocalObjectStorage(tmp_path)
    session_id, key = await _session_with_image(db_conn, checkpointer, storage, test_user["id"])
    await dialogue_message_repository.delete_last_n(db_conn, session_id, 1)

    await purge_user_data(test_pool, checkpointer, storage, test_user["id"])

    assert not (tmp_path / key).exists()


async def test_purge_is_idempotent(
    test_pool: asyncpg.Pool,
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    checkpointer: AsyncPostgresSaver,
    tmp_path: Path,
) -> None:
    storage = LocalObjectStorage(tmp_path)
    session_id, key = await _session_with_image(db_conn, checkpointer, storage, test_user["id"])

    await purge_user_data(test_pool, checkpointer, storage, test_user["id"])
    await purge_user_data(test_pool, checkpointer, storage, test_user["id"])

    assert not await _has_checkpoint(checkpointer, session_id)
    assert not (tmp_path / key).exists()


async def test_purge_user_without_data_succeeds(
    test_pool: asyncpg.Pool, test_user: dict[str, str], checkpointer: AsyncPostgresSaver, tmp_path: Path
) -> None:
    await purge_user_data(test_pool, checkpointer, LocalObjectStorage(tmp_path), test_user["id"])
