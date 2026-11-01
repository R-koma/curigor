from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest

from repositories import (
    dialogue_session_repository,
    feedback_repository,
    note_repository,
    reflection_repository,
    study_memo_repository,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

TOKYO = "Asia/Tokyo"
NOV_1 = date(2026, 11, 1)
NOV_2 = date(2026, 11, 2)


async def _finished_note_session(
    conn: asyncpg.Connection,
    user_id: str,
    *,
    session_type: str = "learning",
    topic: str = "二分探索",
    ended_at: str = "2026-11-01T03:00:00Z",
    is_trial: bool = False,
    status: str = "completed",
    with_note: bool = True,
) -> UUID:
    session_id = uuid4()
    note_id = uuid4()
    if with_note:
        await note_repository.insert(conn, note_id, user_id, topic, "本文", f"{topic}の要約")
    await dialogue_session_repository.create(
        conn,
        session_id=session_id,
        user_id=user_id,
        session_type=session_type,
        graph_version=4,
        note_id=note_id if with_note else None,
        topic=topic,
        is_trial=is_trial,
    )
    await conn.execute(
        "UPDATE dialogue_sessions SET status = $2, ended_at = $3 WHERE id = $1",
        session_id,
        status,
        datetime.fromisoformat(ended_at),
    )
    return session_id


async def _explore_memo(
    conn: asyncpg.Connection, user_id: str, *, topic: str = "素数", created_at: str = "2026-11-01T05:00:00Z"
) -> UUID:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn, session_id=session_id, user_id=user_id, session_type="explore", graph_version=4, topic=topic
    )
    await conn.execute("UPDATE dialogue_sessions SET status = 'completed' WHERE id = $1", session_id)
    memo_id = await study_memo_repository.insert(
        conn,
        user_id=user_id,
        dialogue_session_id=session_id,
        topic=topic,
        source="",
        summary=f"{topic}を教わった",
        overview=[],
        glossary=[],
        questions=[{"question": "なぜ", "answer": "だから"}],
        depth_map={},
    )
    await conn.execute(
        "UPDATE study_memos SET created_at = $2 WHERE id = $1", memo_id, datetime.fromisoformat(created_at)
    )
    return session_id


async def test_returns_completed_learning_review_explore_in_range(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    learning = await _finished_note_session(db_conn, user_id, topic="学習A", ended_at="2026-11-01T01:00:00Z")
    review = await _finished_note_session(
        db_conn, user_id, session_type="review", topic="復習B", ended_at="2026-11-01T02:00:00Z"
    )
    explore = await _explore_memo(db_conn, user_id, topic="探索C", created_at="2026-11-01T03:00:00Z")
    note = await db_conn.fetchrow("SELECT id FROM notes WHERE topic = '学習A' AND user_id = $1", user_id)
    assert note is not None
    await feedback_repository.insert(
        db_conn, note["id"], learning, "medium", "良い", "ここが足りない", improvement_items='[{"x": 1}]'
    )

    items = await reflection_repository.find_items_in_range(db_conn, user_id, NOV_1, NOV_2, TOKYO)

    assert [(i["session_id"], i["session_type"], i["topic"]) for i in items] == [
        (learning, "learning", "学習A"),
        (review, "review", "復習B"),
        (explore, "explore", "探索C"),
    ]
    assert items[0]["improvements"] == "ここが足りない"
    assert items[0]["improvement_items"] == [{"x": 1}]
    assert items[0]["memo_id"] is None
    assert items[2]["note_id"] is None
    assert items[2]["memo_id"] is not None
    assert items[2]["questions"] == [{"question": "なぜ", "answer": "だから"}]
    assert items[2]["summary"] == "探索Cを教わった"
    assert all(i["day"] == NOV_1 for i in items)


async def test_excludes_trial_failed_synthesis_and_deleted_note(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    await _finished_note_session(db_conn, user_id, is_trial=True)
    await _finished_note_session(db_conn, user_id, status="failed")
    await _finished_note_session(db_conn, user_id, session_type="synthesis")
    await _finished_note_session(db_conn, user_id, with_note=False)

    assert await reflection_repository.find_items_in_range(db_conn, user_id, NOV_1, NOV_2, TOKYO) == []


async def test_day_uses_timezone(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    await _finished_note_session(db_conn, user_id, ended_at="2026-10-31T15:30:00Z")

    items = await reflection_repository.find_items_in_range(db_conn, user_id, NOV_1, NOV_2, TOKYO)
    assert [i["day"] for i in items] == [NOV_1]

    utc_items = await reflection_repository.find_items_in_range(db_conn, user_id, NOV_1, NOV_2, "UTC")
    assert utc_items == []


async def test_explore_uses_memo_created_at(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    session_id = await _explore_memo(db_conn, user_id, created_at="2026-11-01T05:00:00Z")
    ended_at = await db_conn.fetchval("SELECT ended_at FROM dialogue_sessions WHERE id = $1", session_id)
    assert ended_at is None

    items = await reflection_repository.find_items_in_range(db_conn, user_id, NOV_1, NOV_2, TOKYO)
    assert [i["session_id"] for i in items] == [session_id]
    assert await reflection_repository.find_items_in_range(db_conn, user_id, NOV_2, date(2026, 11, 3), TOKYO) == []


async def test_other_user_items_not_returned(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    other_id = "other-user-reflection"
    await db_conn.execute(
        """--sql
        INSERT INTO "user" (id, name, email, "emailVerified") VALUES ($1, 'Other', 'other-r@example.com', true)
        ON CONFLICT (id) DO NOTHING
        """,
        other_id,
    )
    await _finished_note_session(db_conn, other_id)
    await _explore_memo(db_conn, other_id)

    assert await reflection_repository.find_items_in_range(db_conn, test_user["id"], NOV_1, NOV_2, TOKYO) == []
    assert len(await reflection_repository.find_items_in_range(db_conn, other_id, NOV_1, NOV_2, TOKYO)) == 2


async def test_mark_viewed_upserts(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    await reflection_repository.mark_viewed(db_conn, user_id, NOV_1)
    first = (await reflection_repository.find_viewed_at(db_conn, user_id, NOV_1, NOV_2))[NOV_1]
    await db_conn.execute("UPDATE reflection_views SET viewed_at = viewed_at - interval '1 hour'")

    await reflection_repository.mark_viewed(db_conn, user_id, NOV_1)

    viewed = await reflection_repository.find_viewed_at(db_conn, user_id, NOV_1, NOV_2)
    assert len(viewed) == 1
    assert viewed[NOV_1] > first - timedelta(minutes=1)
    assert await db_conn.fetchval("SELECT count(*) FROM reflection_views WHERE user_id = $1", user_id) == 1
