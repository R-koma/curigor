import asyncio
from uuid import UUID, uuid4

import asyncpg
import pytest

from repositories import dialogue_session_repository, transcription_usage_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")

_TZ = "Asia/Tokyo"
_MODEL = "gpt-transcribe"


async def _seed_session(conn: asyncpg.Connection, user_id: str) -> UUID:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=conn, session_id=session_id, user_id=user_id, session_type="learning", graph_version=2
    )
    return session_id


async def test_sums_todays_seconds(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])

    await transcription_usage_repository.insert(db_conn, test_user["id"], session_id, 2048, 1.5, _MODEL)
    await transcription_usage_repository.insert(db_conn, test_user["id"], session_id, 4096, 2.25, _MODEL)

    assert await transcription_usage_repository.sum_seconds_today_by_user(db_conn, test_user["id"], _TZ) == 3.75


async def test_ignores_usage_before_today_in_the_user_timezone(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])
    await db_conn.execute(
        """--sql
        INSERT INTO transcription_usages (user_id, dialogue_session_id, audio_bytes, audio_seconds, model, created_at)
        VALUES ($1, $2, 1, 1, $3, (date_trunc('day', NOW() AT TIME ZONE $4) AT TIME ZONE $4) - INTERVAL '1 minute')
        """,
        test_user["id"],
        session_id,
        _MODEL,
        _TZ,
    )

    assert await transcription_usage_repository.sum_seconds_today_by_user(db_conn, test_user["id"], _TZ) == 0.0


async def test_ignores_other_users(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    other_user_id = "test-user-002"
    await db_conn.execute(
        """--sql
        INSERT INTO "user" (id, name, email, "emailVerified")
        VALUES ($1, 'Other User', 'other@example.com', true)
        ON CONFLICT (id) DO NOTHING
        """,
        other_user_id,
    )
    session_id = await _seed_session(db_conn, other_user_id)
    await transcription_usage_repository.insert(db_conn, other_user_id, session_id, 2048, 1.0, _MODEL)

    assert await transcription_usage_repository.sum_seconds_today_by_user(db_conn, test_user["id"], _TZ) == 0.0


async def test_usage_survives_session_deletion(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])
    await transcription_usage_repository.insert(db_conn, test_user["id"], session_id, 2048, 1.0, _MODEL)

    await db_conn.execute("DELETE FROM dialogue_sessions WHERE id = $1", session_id)

    assert await transcription_usage_repository.sum_seconds_today_by_user(db_conn, test_user["id"], _TZ) == 1.0


async def test_counts_usage_recorded_without_a_session(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    await transcription_usage_repository.insert(db_conn, test_user["id"], None, 2048, 1.0, _MODEL)

    assert await transcription_usage_repository.sum_seconds_today_by_user(db_conn, test_user["id"], _TZ) == 1.0


async def test_reserve_records_the_seconds_under_the_limit(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])

    usage_id = await transcription_usage_repository.reserve(
        db_conn, test_user["id"], session_id, 2048, 1.5, _MODEL, _TZ, 10.0
    )

    assert usage_id is not None
    assert await transcription_usage_repository.sum_seconds_today_by_user(db_conn, test_user["id"], _TZ) == 1.5


async def test_reserve_refuses_at_the_limit_without_recording(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    await transcription_usage_repository.insert(db_conn, test_user["id"], None, 2048, 10.0, _MODEL)

    usage_id = await transcription_usage_repository.reserve(
        db_conn, test_user["id"], None, 2048, 1.5, _MODEL, _TZ, 10.0
    )

    assert usage_id is None
    assert await transcription_usage_repository.sum_seconds_today_by_user(db_conn, test_user["id"], _TZ) == 10.0


async def test_concurrent_reservations_cannot_pass_the_limit_together(
    test_pool: asyncpg.Pool, test_user: dict[str, str]
) -> None:
    async def reserve() -> UUID | None:
        async with test_pool.acquire() as conn:
            return await transcription_usage_repository.reserve(
                conn, test_user["id"], None, 2048, 6.0, _MODEL, _TZ, 10.0
            )

    results = await asyncio.gather(*(reserve() for _ in range(5)))

    assert sum(result is not None for result in results) == 2
    async with test_pool.acquire() as conn:
        assert await transcription_usage_repository.sum_seconds_today_by_user(conn, test_user["id"], _TZ) == 12.0


async def test_cancel_deletes_only_that_reservation(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    cancelled = await transcription_usage_repository.reserve(
        db_conn, test_user["id"], None, 2048, 1.5, _MODEL, _TZ, 10.0
    )
    await transcription_usage_repository.reserve(db_conn, test_user["id"], None, 2048, 2.25, _MODEL, _TZ, 10.0)
    assert cancelled is not None

    await transcription_usage_repository.cancel(db_conn, cancelled)

    assert await transcription_usage_repository.sum_seconds_today_by_user(db_conn, test_user["id"], _TZ) == 2.25
