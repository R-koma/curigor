from collections.abc import AsyncGenerator
from datetime import datetime
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from core import database
from core.database import DBConnection
from main import app
from repositories import dialogue_session_repository, note_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")

USER_A = "reflection-route-user-a"
USER_B = "reflection-route-user-b"
DAY = "2026-10-14"
WEEK_START = "2026-10-12"


async def _create_user(conn: DBConnection, user_id: str) -> None:
    await conn.execute(
        'INSERT INTO "user" (id, name, email, "emailVerified") VALUES ($1, $2, $3, true) ON CONFLICT (id) DO NOTHING',
        user_id,
        user_id,
        f"{user_id}@example.com",
    )


async def _finished_session(conn: DBConnection, user_id: str, topic: str) -> None:
    session_id = uuid4()
    note_id = uuid4()
    await note_repository.insert(conn, note_id, user_id, topic, "本文", f"{topic}の要約")
    await dialogue_session_repository.create(
        conn,
        session_id=session_id,
        user_id=user_id,
        session_type="learning",
        graph_version=4,
        note_id=note_id,
        topic=topic,
    )
    await conn.execute(
        "UPDATE dialogue_sessions SET status = 'completed', ended_at = $2 WHERE id = $1",
        session_id,
        datetime.fromisoformat("2026-10-14T03:00:00Z"),
    )


@pytest_asyncio.fixture(loop_scope="session")
async def client(test_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[AsyncClient]:
    async with test_pool.acquire() as conn:
        await _create_user(conn, USER_A)
        await _create_user(conn, USER_B)
        await _finished_session(conn, USER_A, "二分探索")
    monkeypatch.setattr(database, "_pool", test_pool)
    app.dependency_overrides[get_current_user] = lambda: USER_A
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_get_day_returns_groups(client: AsyncClient) -> None:
    response = await client.get(f"/api/reflections/days/{DAY}")

    assert response.status_code == 200
    body = response.json()
    assert body["day"] == DAY
    assert body["groups"][0]["session_type"] == "learning"
    assert body["groups"][0]["topics"][0]["topic"] == "二分探索"


async def test_get_week_days_marks_unread_then_view_clears(client: AsyncClient) -> None:
    def target(response_json: dict[str, list[dict[str, object]]]) -> dict[str, object]:
        return next(d for d in response_json["days"] if d["day"] == DAY)

    first = await client.get(f"/api/reflections/weeks/{WEEK_START}/days")
    assert first.status_code == 200
    assert len(first.json()["days"]) == 7
    assert target(first.json()) == {"day": DAY, "has_learning": True, "unread": True}

    viewed = await client.put(f"/api/reflections/days/{DAY}/view")
    assert viewed.status_code == 204

    after = await client.get(f"/api/reflections/weeks/{WEEK_START}/days")
    assert target(after.json())["unread"] is False


async def test_week_start_not_monday_is_rounded(client: AsyncClient) -> None:
    response = await client.get(f"/api/reflections/weeks/{DAY}/days")

    assert response.status_code == 200
    assert response.json()["days"][0]["day"] == WEEK_START


async def test_future_day_is_empty_and_invalid_date_is_422(client: AsyncClient) -> None:
    future = await client.get("/api/reflections/days/2999-01-01")
    assert future.status_code == 200
    assert future.json()["groups"] == []

    invalid = await client.get("/api/reflections/days/2026-13-01")
    assert invalid.status_code == 422


async def test_other_user_sees_nothing(client: AsyncClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: USER_B

    day = await client.get(f"/api/reflections/days/{DAY}")
    week = await client.get(f"/api/reflections/weeks/{WEEK_START}/days")

    assert day.json()["groups"] == []
    assert all(not d["has_learning"] and not d["unread"] for d in week.json()["days"])
