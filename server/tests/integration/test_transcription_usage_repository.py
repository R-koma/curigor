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


async def test_counts_todays_usage(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])

    await transcription_usage_repository.insert(db_conn, test_user["id"], session_id, 2048, _MODEL)
    await transcription_usage_repository.insert(db_conn, test_user["id"], session_id, 4096, _MODEL)

    assert await transcription_usage_repository.count_today_by_user(db_conn, test_user["id"], _TZ) == 2


async def test_ignores_usage_before_today_in_the_user_timezone(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])
    await db_conn.execute(
        """--sql
        INSERT INTO transcription_usages (user_id, dialogue_session_id, audio_bytes, model, created_at)
        VALUES ($1, $2, 1, $3, (date_trunc('day', NOW() AT TIME ZONE $4) AT TIME ZONE $4) - INTERVAL '1 minute')
        """,
        test_user["id"],
        session_id,
        _MODEL,
        _TZ,
    )

    assert await transcription_usage_repository.count_today_by_user(db_conn, test_user["id"], _TZ) == 0


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
    await transcription_usage_repository.insert(db_conn, other_user_id, session_id, 2048, _MODEL)

    assert await transcription_usage_repository.count_today_by_user(db_conn, test_user["id"], _TZ) == 0


async def test_usage_survives_session_deletion(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])
    await transcription_usage_repository.insert(db_conn, test_user["id"], session_id, 2048, _MODEL)

    await db_conn.execute("DELETE FROM dialogue_sessions WHERE id = $1", session_id)

    assert await transcription_usage_repository.count_today_by_user(db_conn, test_user["id"], _TZ) == 1
