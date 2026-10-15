from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from repositories import dialogue_session_repository
from services.orphaned_session_data import purge_orphaned_session_data, purge_orphaned_session_data_in_background
from storage import dialogue_image_prefix
from storage.local import LocalObjectStorage
from tests.integration.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session")
async def checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    async with AsyncPostgresSaver.from_conn_string(TEST_DATABASE_URL) as saver:
        await saver.setup()
        yield saver


async def _write_session_data(saver: AsyncPostgresSaver, storage: LocalObjectStorage, session_id: UUID) -> str:
    key = f"{dialogue_image_prefix(session_id)}{uuid4()}/0.png"
    await storage.put(key, b"png", "image/png")
    await saver.aput({"configurable": {"thread_id": str(session_id), "checkpoint_ns": ""}}, empty_checkpoint(), {}, {})
    return key


async def _has_checkpoint(saver: AsyncPostgresSaver, session_id: UUID) -> bool:
    return await saver.aget_tuple({"configurable": {"thread_id": str(session_id)}}) is not None


async def test_purge_removes_data_without_a_session_and_keeps_the_rest(
    test_pool: asyncpg.Pool,
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    checkpointer: AsyncPostgresSaver,
    tmp_path: Path,
) -> None:
    storage = LocalObjectStorage(tmp_path)
    kept = uuid4()
    await dialogue_session_repository.create(db_conn, kept, test_user["id"], "learning", graph_version=1)
    kept_key = await _write_session_data(checkpointer, storage, kept)
    orphan = uuid4()
    orphan_key = await _write_session_data(checkpointer, storage, orphan)

    await purge_orphaned_session_data(test_pool, checkpointer, storage)

    assert await _has_checkpoint(checkpointer, kept)
    assert (tmp_path / kept_key).exists()
    assert not await _has_checkpoint(checkpointer, orphan)
    assert not (tmp_path / dialogue_image_prefix(orphan)).exists()
    assert not (tmp_path / orphan_key).exists()


async def test_purge_removes_data_of_a_session_deleted_later(
    test_pool: asyncpg.Pool,
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    checkpointer: AsyncPostgresSaver,
    tmp_path: Path,
) -> None:
    storage = LocalObjectStorage(tmp_path)
    session_id = uuid4()
    await dialogue_session_repository.create(db_conn, session_id, test_user["id"], "learning", graph_version=1)
    key = await _write_session_data(checkpointer, storage, session_id)
    await db_conn.execute("DELETE FROM dialogue_sessions WHERE id = $1", session_id)

    await purge_orphaned_session_data(test_pool, checkpointer, storage)

    assert not await _has_checkpoint(checkpointer, session_id)
    assert not (tmp_path / key).exists()


async def test_purge_leaves_non_session_directories_alone(
    test_pool: asyncpg.Pool, checkpointer: AsyncPostgresSaver, tmp_path: Path
) -> None:
    storage = LocalObjectStorage(tmp_path)
    await storage.put("dialogue_images/not-a-uuid/0.png", b"x", "image/png")

    await purge_orphaned_session_data(test_pool, checkpointer, storage)

    assert (tmp_path / "dialogue_images/not-a-uuid/0.png").exists()


async def test_purge_succeeds_when_nothing_is_there(
    test_pool: asyncpg.Pool, checkpointer: AsyncPostgresSaver, tmp_path: Path
) -> None:
    await purge_orphaned_session_data(test_pool, checkpointer, LocalObjectStorage(tmp_path))


async def test_purge_leaves_non_canonical_uuid_directories_alone(
    test_pool: asyncpg.Pool, checkpointer: AsyncPostgresSaver, tmp_path: Path
) -> None:
    storage = LocalObjectStorage(tmp_path)
    name = uuid4().hex
    await storage.put(f"dialogue_images/{name}/0.png", b"x", "image/png")

    await purge_orphaned_session_data(test_pool, checkpointer, storage)

    assert (tmp_path / f"dialogue_images/{name}/0.png").exists()


async def test_background_purge_logs_failures_instead_of_raising(
    test_pool: asyncpg.Pool, checkpointer: AsyncPostgresSaver, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    class FailingStorage(LocalObjectStorage):
        async def list_child_prefixes(self, prefix: str) -> list[str]:
            raise OSError("storage unavailable")

    await purge_orphaned_session_data_in_background(test_pool, checkpointer, FailingStorage(tmp_path))

    assert "failed to purge orphaned session data" in caplog.text
