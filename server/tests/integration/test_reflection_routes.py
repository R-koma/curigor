from collections.abc import AsyncGenerator, AsyncIterator, Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from core import database
from core.database import DBConnection
from core.terms import TERMS_VERSION
from graph.output_schemas import ReflectionQuizQuestion
from main import app
from repositories import dialogue_session_repository, feedback_repository, note_repository, user_consent_repository
from services.reflection_generation import ReflectionEmptyError, ReflectionGenerationError, ReflectionLimitError
from speech import get_synthesizer

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


async def _finished_session(
    conn: DBConnection, user_id: str, topic: str, ended_at: str = "2026-10-14T03:00:00Z"
) -> tuple[UUID, UUID]:
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
        datetime.fromisoformat(ended_at),
    )
    return session_id, note_id


@pytest_asyncio.fixture(loop_scope="session")
async def client(test_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[AsyncClient]:
    async with test_pool.acquire() as conn:
        await _create_user(conn, USER_A)
        await _create_user(conn, USER_B)
        await _finished_session(conn, USER_A, "二分探索")
        await user_consent_repository.record(conn, USER_A, TERMS_VERSION)
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


async def test_get_week_reflection(client: AsyncClient, test_pool: asyncpg.Pool) -> None:
    async with test_pool.acquire() as conn:
        session_id, note_id = await _finished_session(conn, USER_A, "TCP", "2026-10-16T03:00:00Z")
        await feedback_repository.insert(conn, note_id, session_id, "medium", "よい", "再送の条件")
        await _finished_session(conn, USER_A, "来週の話題", "2026-10-19T03:00:00Z")

    response = await client.get(f"/api/reflections/weeks/{DAY}")

    assert response.status_code == 200
    assert response.json() == {
        "week_start": WEEK_START,
        "days": [
            {"day": "2026-10-14", "topics": [{"session_type": "learning", "topic": "二分探索"}]},
            {"day": "2026-10-16", "topics": [{"session_type": "learning", "topic": "TCP"}]},
        ],
        "struggles": [{"topic": "TCP", "kind": "struggle", "text": "再送の条件", "answer": None}],
    }


async def test_other_user_sees_no_week_reflection(client: AsyncClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: USER_B

    response = await client.get(f"/api/reflections/weeks/{WEEK_START}")

    assert response.json() == {"week_start": WEEK_START, "days": [], "struggles": []}


class _FakeSynthesizer:
    model = "fake-synthesizer"

    async def stream(self, text: str, speed: float) -> AsyncIterator[bytes]:
        yield b"\x00\x00"


@pytest.fixture
def fake_synthesizer() -> Generator[_FakeSynthesizer]:
    synthesizer = _FakeSynthesizer()
    app.dependency_overrides[get_synthesizer] = lambda: synthesizer
    yield synthesizer
    app.dependency_overrides.pop(get_synthesizer, None)


async def test_script_endpoint_returns_sentences(client: AsyncClient) -> None:
    with patch(
        "api.routes.reflection.reflection_generation.get_or_create_script",
        new=AsyncMock(return_value=["一文目。", "二文目。"]),
    ):
        response = await client.post(f"/api/reflections/day/{DAY}/script")

    assert response.status_code == 200
    assert response.json() == {"sentences": ["一文目。", "二文目。"]}


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (ReflectionEmptyError, 404, "reflection_empty"),
        (ReflectionLimitError, 429, "daily_reflection_limit_reached"),
        (ReflectionGenerationError, 502, "reflection_generation_failed"),
    ],
)
async def test_script_endpoint_maps_errors(
    client: AsyncClient, error: type[Exception], status_code: int, code: str
) -> None:
    with patch("api.routes.reflection.reflection_generation.get_or_create_script", new=AsyncMock(side_effect=error)):
        response = await client.post(f"/api/reflections/week/{WEEK_START}/script")

    assert response.status_code == status_code
    assert response.json()["code"] == code


async def test_quiz_endpoint_returns_questions(client: AsyncClient) -> None:
    question = ReflectionQuizQuestion(question="問", choices=["a", "b", "c", "d"], answer_index=2, explanation="理由")
    with patch(
        "api.routes.reflection.reflection_generation.get_or_create_quiz",
        new=AsyncMock(return_value=[question]),
    ):
        response = await client.post(f"/api/reflections/day/{DAY}/quiz")

    assert response.status_code == 200
    assert response.json() == {
        "questions": [{"question": "問", "choices": ["a", "b", "c", "d"], "answer_index": 2, "explanation": "理由"}]
    }


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (ReflectionEmptyError, 404, "reflection_empty"),
        (ReflectionLimitError, 429, "daily_reflection_limit_reached"),
        (ReflectionGenerationError, 502, "reflection_generation_failed"),
    ],
)
async def test_quiz_endpoint_maps_errors(
    client: AsyncClient, error: type[Exception], status_code: int, code: str
) -> None:
    with patch("api.routes.reflection.reflection_generation.get_or_create_quiz", new=AsyncMock(side_effect=error)):
        response = await client.post(f"/api/reflections/week/{WEEK_START}/quiz")

    assert response.status_code == status_code
    assert response.json()["code"] == code


async def test_reflection_speech_streams_and_counts_usage(
    client: AsyncClient, test_pool: asyncpg.Pool, fake_synthesizer: _FakeSynthesizer
) -> None:
    async with test_pool.acquire() as conn:
        before = await conn.fetchval(
            "SELECT count(*) FROM speech_usages WHERE user_id = $1 AND dialogue_session_id IS NULL", USER_A
        )

    response = await client.post("/api/reflections/speech", json={"text": "こんにちは。"})

    assert response.status_code == 200
    assert response.content == b"\x00\x00"
    async with test_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT characters FROM speech_usages WHERE user_id = $1 AND dialogue_session_id IS NULL", USER_A
        )
    assert len(rows) == before + 1
    assert rows[-1]["characters"] == len("こんにちは。")


async def test_reflection_speech_rejects_501_chars(client: AsyncClient, fake_synthesizer: _FakeSynthesizer) -> None:
    response = await client.post("/api/reflections/speech", json={"text": "あ" * 501})

    assert response.status_code == 400
    assert response.json()["code"] == "speech_text_invalid"


async def test_requires_consent(client: AsyncClient, fake_synthesizer: _FakeSynthesizer) -> None:
    app.dependency_overrides[get_current_user] = lambda: USER_B

    script = await client.post(f"/api/reflections/day/{DAY}/script")
    quiz = await client.post(f"/api/reflections/day/{DAY}/quiz")
    speech = await client.post("/api/reflections/speech", json={"text": "こんにちは"})

    assert script.status_code == 403
    assert script.json()["code"] == "consent_required"
    assert quiz.status_code == 403
    assert speech.status_code == 403
