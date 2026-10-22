from uuid import UUID, uuid4

import asyncpg
import pytest

from repositories import dialogue_session_repository, transcript_format_usage_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")

_TZ = "Asia/Tokyo"
_MODEL = "gpt-6-luna"


async def _seed_session(conn: asyncpg.Connection, user_id: str) -> UUID:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=conn, session_id=session_id, user_id=user_id, session_type="learning", graph_version=2
    )
    return session_id


async def test_sums_todays_characters(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])

    await transcript_format_usage_repository.insert(db_conn, test_user["id"], session_id, 120, _MODEL)
    await transcript_format_usage_repository.insert(db_conn, test_user["id"], session_id, 80, _MODEL)

    assert await transcript_format_usage_repository.sum_today_by_user(db_conn, test_user["id"], _TZ) == 200


async def test_returns_zero_without_usage(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    assert await transcript_format_usage_repository.sum_today_by_user(db_conn, test_user["id"], _TZ) == 0


async def test_ignores_usage_before_today_in_the_user_timezone(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])
    await db_conn.execute(
        """--sql
        INSERT INTO transcript_format_usages (user_id, dialogue_session_id, characters, model, created_at)
        VALUES ($1, $2, 300, $3, (date_trunc('day', NOW() AT TIME ZONE $4) AT TIME ZONE $4) - INTERVAL '1 minute')
        """,
        test_user["id"],
        session_id,
        _MODEL,
        _TZ,
    )

    assert await transcript_format_usage_repository.sum_today_by_user(db_conn, test_user["id"], _TZ) == 0


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
    await transcript_format_usage_repository.insert(db_conn, other_user_id, session_id, 500, _MODEL)

    assert await transcript_format_usage_repository.sum_today_by_user(db_conn, test_user["id"], _TZ) == 0


async def test_usage_survives_session_deletion(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])
    await transcript_format_usage_repository.insert(db_conn, test_user["id"], session_id, 500, _MODEL)

    await db_conn.execute("DELETE FROM dialogue_sessions WHERE id = $1", session_id)

    assert await transcript_format_usage_repository.sum_today_by_user(db_conn, test_user["id"], _TZ) == 500
