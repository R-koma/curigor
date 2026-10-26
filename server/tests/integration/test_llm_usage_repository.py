import asyncio
from uuid import UUID

import asyncpg
import pytest

from repositories import llm_usage_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")

_TZ = "Asia/Tokyo"


async def test_reserve_records_an_operation_under_the_limit(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    usage_id = await llm_usage_repository.reserve(db_conn, test_user["id"], "turn", _TZ, 2)

    assert usage_id is not None
    assert await llm_usage_repository.count_today(db_conn, test_user["id"], "turn", _TZ) == 1


async def test_reserve_refuses_at_the_limit_without_recording(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    await llm_usage_repository.reserve(db_conn, test_user["id"], "turn", _TZ, 2)
    await llm_usage_repository.reserve(db_conn, test_user["id"], "turn", _TZ, 2)

    third = await llm_usage_repository.reserve(db_conn, test_user["id"], "turn", _TZ, 2)

    assert third is None
    assert await llm_usage_repository.count_today(db_conn, test_user["id"], "turn", _TZ) == 2


async def test_operations_are_counted_separately(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    assert await llm_usage_repository.reserve(db_conn, test_user["id"], "turn", _TZ, 1) is not None
    assert await llm_usage_repository.reserve(db_conn, test_user["id"], "turn", _TZ, 1) is None

    assert await llm_usage_repository.reserve(db_conn, test_user["id"], "session_start", _TZ, 1) is not None


async def test_usage_before_today_in_the_timezone_is_not_counted(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    await db_conn.execute(
        """--sql
        INSERT INTO llm_usages (user_id, operation, created_at)
        VALUES ($1, 'turn', (date_trunc('day', NOW() AT TIME ZONE $2) AT TIME ZONE $2) - INTERVAL '30 minutes')
        """,
        test_user["id"],
        _TZ,
    )

    assert await llm_usage_repository.count_today(db_conn, test_user["id"], "turn", _TZ) == 0


async def test_concurrent_reservations_cannot_pass_the_limit_together(
    test_pool: asyncpg.Pool, test_user: dict[str, str]
) -> None:
    async def reserve() -> UUID | None:
        async with test_pool.acquire() as conn:
            return await llm_usage_repository.reserve(conn, test_user["id"], "turn", _TZ, 3)

    results = await asyncio.gather(*(reserve() for _ in range(5)))

    assert sum(result is not None for result in results) == 3
    async with test_pool.acquire() as conn:
        assert await llm_usage_repository.count_today(conn, test_user["id"], "turn", _TZ) == 3


async def test_cancel_deletes_only_that_reservation(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    cancelled = await llm_usage_repository.reserve(db_conn, test_user["id"], "turn", _TZ, 5)
    await llm_usage_repository.reserve(db_conn, test_user["id"], "turn", _TZ, 5)
    assert cancelled is not None

    await llm_usage_repository.cancel(db_conn, cancelled)

    assert await llm_usage_repository.count_today(db_conn, test_user["id"], "turn", _TZ) == 1
