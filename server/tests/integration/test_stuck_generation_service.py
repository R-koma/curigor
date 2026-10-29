import asyncio
import logging
from datetime import timedelta
from uuid import uuid4

import asyncpg
import pytest

from repositories import dialogue_session_repository
from services.stuck_generation import reset_stuck_generations, reset_stuck_generations_periodically

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _generating_session(conn: asyncpg.Connection, user_id: str, started_ago: timedelta | None) -> str:
    session_id = uuid4()
    await dialogue_session_repository.create(conn, session_id, user_id, "learning", graph_version=1)
    await dialogue_session_repository.update_status(conn, session_id, "generate_note")
    if started_ago is not None:
        await conn.execute(
            "UPDATE dialogue_sessions SET generation_started_at = NOW() - $2::interval WHERE id = $1",
            session_id,
            started_ago,
        )
    return str(session_id)


async def _status(conn: asyncpg.Connection, session_id: str) -> str:
    return str(await conn.fetchval("SELECT status FROM dialogue_sessions WHERE id = $1", session_id))


async def _status_once_settled(
    conn: asyncpg.Connection, session_id: str, expected: str, timeout_seconds: float = 2.0
) -> str:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while (status := await _status(conn, session_id)) != expected and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.01)
    return status


async def test_sweep_resets_only_stale_generations_and_logs_them(
    test_pool: asyncpg.Pool,
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    fresh = await _generating_session(db_conn, test_user["id"], None)
    stale = await _generating_session(db_conn, test_user["id"], timedelta(minutes=4))

    with caplog.at_level(logging.WARNING, logger="services.stuck_generation"):
        count = await reset_stuck_generations(test_pool, timedelta(minutes=3))

    assert count == 1
    assert await _status(db_conn, fresh) == "generate_note"
    assert await _status(db_conn, stale) == "failed"
    assert any(stale in record.getMessage() for record in caplog.records)


async def test_sweep_is_quiet_when_nothing_is_stuck(
    test_pool: asyncpg.Pool, db_conn: asyncpg.Connection, test_user: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    await _generating_session(db_conn, test_user["id"], None)

    with caplog.at_level(logging.INFO, logger="services.stuck_generation"):
        count = await reset_stuck_generations(test_pool, timedelta(minutes=3))

    assert count == 0 and caplog.records == []


async def _cancel(task: asyncio.Task[None]) -> None:
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_periodic_sweep_runs_once_at_startup(
    test_pool: asyncpg.Pool, db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    stale = await _generating_session(db_conn, test_user["id"], timedelta(minutes=4))

    task = asyncio.create_task(reset_stuck_generations_periodically(test_pool, interval_seconds=3600))
    try:
        assert await _status_once_settled(db_conn, stale, "failed") == "failed"
    finally:
        await _cancel(task)


async def test_periodic_sweep_keeps_running_after_startup(
    test_pool: asyncpg.Pool, db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    stale = await _generating_session(db_conn, test_user["id"], timedelta(minutes=4))

    task = asyncio.create_task(reset_stuck_generations_periodically(test_pool, interval_seconds=0.05))
    try:
        assert await _status_once_settled(db_conn, stale, "failed") == "failed"
        later = await _generating_session(db_conn, test_user["id"], timedelta(minutes=4))
        assert await _status_once_settled(db_conn, later, "failed") == "failed"
    finally:
        await _cancel(task)
