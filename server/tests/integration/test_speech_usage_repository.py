import asyncio
from uuid import UUID, uuid4

import asyncpg
import pytest

from core.database import DBConnection
from repositories import dialogue_session_repository, speech_usage_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")

_TZ = "Asia/Tokyo"
_MODEL = "gpt-4o-mini-tts"


async def _seed_session(conn: DBConnection, user_id: str) -> UUID:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=conn, session_id=session_id, user_id=user_id, session_type="learning", graph_version=2
    )
    return session_id


async def test_sums_todays_characters(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])

    await speech_usage_repository.insert(db_conn, test_user["id"], session_id, 120, _MODEL)
    await speech_usage_repository.insert(db_conn, test_user["id"], session_id, 80, _MODEL)

    assert await speech_usage_repository.sum_today_by_user(db_conn, test_user["id"], _TZ) == 200


async def test_returns_zero_without_usage(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    assert await speech_usage_repository.sum_today_by_user(db_conn, test_user["id"], _TZ) == 0


async def test_ignores_usage_before_today_in_the_user_timezone(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])
    await db_conn.execute(
        """--sql
        INSERT INTO speech_usages (user_id, dialogue_session_id, characters, model, created_at)
        VALUES ($1, $2, 300, $3, (date_trunc('day', NOW() AT TIME ZONE $4) AT TIME ZONE $4) - INTERVAL '1 minute')
        """,
        test_user["id"],
        session_id,
        _MODEL,
        _TZ,
    )

    assert await speech_usage_repository.sum_today_by_user(db_conn, test_user["id"], _TZ) == 0


async def test_reserve_records_the_characters_under_the_limit(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])

    usage_id = await speech_usage_repository.reserve(db_conn, test_user["id"], session_id, 120, _MODEL, _TZ, 1000)

    assert usage_id is not None
    assert await speech_usage_repository.sum_today_by_user(db_conn, test_user["id"], _TZ) == 120


async def test_reserve_refuses_at_the_limit_without_recording(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])
    await speech_usage_repository.insert(db_conn, test_user["id"], session_id, 1000, _MODEL)

    usage_id = await speech_usage_repository.reserve(db_conn, test_user["id"], session_id, 120, _MODEL, _TZ, 1000)

    assert usage_id is None
    assert await speech_usage_repository.sum_today_by_user(db_conn, test_user["id"], _TZ) == 1000


async def test_concurrent_reservations_cannot_pass_the_limit_together(
    test_pool: asyncpg.Pool, test_user: dict[str, str]
) -> None:
    async with test_pool.acquire() as conn:
        session_id = await _seed_session(conn, test_user["id"])

    async def reserve() -> UUID | None:
        async with test_pool.acquire() as conn:
            return await speech_usage_repository.reserve(conn, test_user["id"], session_id, 600, _MODEL, _TZ, 1000)

    results = await asyncio.gather(*(reserve() for _ in range(5)))

    assert sum(result is not None for result in results) == 2
    async with test_pool.acquire() as conn:
        assert await speech_usage_repository.sum_today_by_user(conn, test_user["id"], _TZ) == 1200


async def test_cancel_deletes_only_that_reservation(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])
    cancelled = await speech_usage_repository.reserve(db_conn, test_user["id"], session_id, 120, _MODEL, _TZ, 1000)
    await speech_usage_repository.reserve(db_conn, test_user["id"], session_id, 80, _MODEL, _TZ, 1000)
    assert cancelled is not None

    await speech_usage_repository.cancel(db_conn, cancelled)

    assert await speech_usage_repository.sum_today_by_user(db_conn, test_user["id"], _TZ) == 80
