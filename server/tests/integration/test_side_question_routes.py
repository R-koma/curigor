import json
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import BaseMessage

from api.dependencies import get_current_user
from core import config, database
from core.database import DBConnection
from core.terms import TERMS_VERSION
from main import app
from repositories import dialogue_message_repository, dialogue_session_repository, user_consent_repository
from services import side_question as side_question_service

pytestmark = pytest.mark.asyncio(loop_scope="session")

USER = "side-question-user"


@dataclass
class FakeLLM:
    chunks: list[str] = field(default_factory=lambda: ["索引は", "行の位置を指す一覧です"])
    calls: list[Sequence[BaseMessage]] = field(default_factory=list)
    fail: bool = False
    during: Callable[[], Any] | None = None

    async def astream(self, input: Sequence[BaseMessage], config: Any = None, *, task: str) -> AsyncIterator[str]:
        assert task == "explore-side-question"
        self.calls.append(input)
        for i, chunk in enumerate(self.chunks):
            if i == 1 and self.during is not None:
                await self.during()
            if self.fail and i == 1:
                raise RuntimeError("llm down")
            yield chunk


@dataclass
class Env:
    client: AsyncClient
    llm: FakeLLM
    pool: asyncpg.Pool
    session_id: UUID
    anchor_id: UUID


async def _create_user(conn: DBConnection, user_id: str) -> None:
    await conn.execute(
        'INSERT INTO "user" (id, name, email, "emailVerified") VALUES ($1, $2, $3, true) ON CONFLICT (id) DO NOTHING',
        user_id,
        user_id,
        f"{user_id}@example.com",
    )
    await user_consent_repository.record(conn, user_id, TERMS_VERSION)


async def _session(conn: DBConnection, session_type: str = "explore") -> tuple[UUID, UUID]:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn, session_id=session_id, user_id=USER, session_type=session_type, graph_version=2, topic="インデックス"
    )
    await dialogue_message_repository.insert(conn, session_id, "user", "インデックスとは？", 1)
    answer = await dialogue_message_repository.insert(conn, session_id, "assistant", "索引を使って速く探します", 2)
    assert answer is not None
    return session_id, answer["id"]


@pytest_asyncio.fixture(loop_scope="session")
async def env(test_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[Env]:
    async with test_pool.acquire() as conn:
        await _create_user(conn, USER)
        session_id, anchor_id = await _session(conn)
    fake = FakeLLM()
    monkeypatch.setattr(database, "_pool", test_pool)
    monkeypatch.setattr(side_question_service, "llm", fake)
    app.dependency_overrides[get_current_user] = lambda: USER
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield Env(client=client, llm=fake, pool=test_pool, session_id=session_id, anchor_id=anchor_id)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _events(text: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in text.splitlines() if line]


async def _create(env: Env, **overrides: Any) -> Any:
    body = {"anchor_message_id": str(env.anchor_id), "quote": "索引", "occurrence": 0, "content": "索引とは？"}
    body.update(overrides)
    return await env.client.post(f"/api/dialogue-sessions/{env.session_id}/side-questions", json=body)


async def _count(env: Env, table: str) -> int:
    async with env.pool.acquire() as conn:
        return int(await conn.fetchval(f"SELECT COUNT(*) FROM {table}"))  # noqa: S608


async def _turn_usages(env: Env) -> int:
    async with env.pool.acquire() as conn:
        return int(
            await conn.fetchval("SELECT COUNT(*) FROM llm_usages WHERE user_id = $1 AND operation = 'turn'", USER)
        )


async def test_create_streams_started_chunks_end_and_saves_both_messages(env: Env) -> None:
    response = await _create(env)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = _events(response.text)
    assert [e["type"] for e in events] == ["started", "chunk", "chunk", "end"]
    assert "".join(e["content"] for e in events if e["type"] == "chunk") == "索引は行の位置を指す一覧です"
    started = events[0]

    listed = (await env.client.get(f"/api/dialogue-sessions/{env.session_id}/side-questions")).json()
    thread = listed["side_questions"][0]
    assert thread["id"] == started["side_question_id"]
    assert thread["depth"] == 0 and thread["parent_id"] is None
    assert thread["anchor_message_id"] == str(env.anchor_id)
    assert [m["id"] for m in thread["messages"]] == [started["user_message_id"], started["answer_message_id"]]
    assert [m["content"] for m in thread["messages"]] == ["索引とは？", "索引は行の位置を指す一覧です"]
    assert await _turn_usages(env) == 1

    prompt = str(env.llm.calls[0][0].content)
    assert "索引を使って速く探します" in prompt
    assert "「索引」" in prompt


async def test_follow_up_appends_to_existing_thread(env: Env) -> None:
    started = _events((await _create(env)).text)[0]

    response = await env.client.post(
        f"/api/side-questions/{started['side_question_id']}/messages", json={"content": "もう少し詳しく"}
    )

    assert [e["type"] for e in _events(response.text)] == ["started", "chunk", "chunk", "end"]
    thread = (await env.client.get(f"/api/dialogue-sessions/{env.session_id}/side-questions")).json()[
        "side_questions"
    ][0]
    assert [m["role"] for m in thread["messages"]] == ["user", "assistant", "user", "assistant"]
    history = [str(m.content) for m in env.llm.calls[1][1:]]
    assert history == ["索引とは？", "索引は行の位置を指す一覧です", "もう少し詳しく"]


async def test_child_of_side_answer_gets_parent_and_depth_plus_one(env: Env) -> None:
    parent = _events((await _create(env)).text)[0]

    response = await _create(
        env, anchor_message_id=None, anchor_side_message_id=parent["answer_message_id"], quote="目次"
    )

    child = _events(response.text)[0]
    threads = (await env.client.get(f"/api/dialogue-sessions/{env.session_id}/side-questions")).json()[
        "side_questions"
    ]
    created = next(t for t in threads if t["id"] == child["side_question_id"])
    assert created["parent_id"] == parent["side_question_id"]
    assert created["depth"] == 1
    assert created["anchor_side_message_id"] == parent["answer_message_id"]
    prompt = str(env.llm.calls[1][0].content)
    assert "索引は行の位置を指す一覧です" in prompt


async def test_child_at_depth_3_is_rejected_422(env: Env) -> None:
    answer_id = _events((await _create(env)).text)[0]["answer_message_id"]
    for _ in range(3):
        answer_id = _events(
            (await _create(env, anchor_message_id=None, anchor_side_message_id=answer_id, quote="目次")).text
        )[0]["answer_message_id"]
    calls = len(env.llm.calls)
    usages = await _turn_usages(env)

    response = await _create(env, anchor_message_id=None, anchor_side_message_id=answer_id, quote="目次")

    assert response.status_code == 422
    assert response.json()["code"] == "side_question_too_deep"
    assert len(env.llm.calls) == calls
    assert await _turn_usages(env) == usages


async def test_non_explore_session_is_rejected_409(env: Env) -> None:
    async with env.pool.acquire() as conn:
        env.session_id, env.anchor_id = await _session(conn, "learning")

    response = await _create(env)

    assert response.status_code == 409
    assert response.json()["code"] == "session_not_explore"
    assert env.llm.calls == []


@pytest.mark.parametrize("session_status", ["completed", "abandoned", "generate_note"])
async def test_ended_session_is_rejected_409_without_llm_call_and_refunds_usage(env: Env, session_status: str) -> None:
    started = _events((await _create(env)).text)[0]
    async with env.pool.acquire() as conn:
        await dialogue_session_repository.update_status(conn, env.session_id, session_status)
    usages = await _turn_usages(env)

    created = await _create(env)
    followed = await env.client.post(
        f"/api/side-questions/{started['side_question_id']}/messages", json={"content": "続き"}
    )

    for response in (created, followed):
        assert response.status_code == 409
        assert response.json()["code"] == "session_not_active"
    assert len(env.llm.calls) == 1
    assert await _turn_usages(env) == usages


async def test_quote_over_300_chars_is_rejected_422(env: Env) -> None:
    response = await _create(env, quote="あ" * 301)

    assert response.status_code == 422
    assert env.llm.calls == []


async def test_both_anchors_are_rejected_422(env: Env) -> None:
    response = await _create(env, anchor_side_message_id=str(uuid4()))

    assert response.status_code == 422


async def test_anchor_of_user_message_is_not_found(env: Env) -> None:
    async with env.pool.acquire() as conn:
        user_row = await conn.fetchval(
            "SELECT id FROM dialogue_messages WHERE dialogue_session_id = $1 AND role = 'user'", env.session_id
        )

    response = await _create(env, anchor_message_id=str(user_row))

    assert response.status_code == 404
    assert response.json()["code"] == "side_question_anchor_not_found"


async def test_usage_limit_reached_is_rejected_without_llm_call(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "DAILY_TURN_LIMIT", 0)

    response = await _create(env)

    assert response.status_code == 429
    assert response.json()["code"] == "daily_turn_limit_reached"
    assert env.llm.calls == []
    assert await _count(env, "side_questions") == 0


async def test_llm_failure_emits_error_and_leaves_no_rows_and_keeps_usage(env: Env) -> None:
    env.llm.fail = True

    response = await _create(env)

    events = _events(response.text)
    assert events[0]["type"] == "started"
    assert events[-1] == {"type": "error", "code": "side_question_failed", "detail": events[-1]["detail"]}
    assert await _count(env, "side_questions") == 0
    assert await _count(env, "side_question_messages") == 0
    assert await _turn_usages(env) == 1


async def test_follow_up_failure_keeps_earlier_messages(env: Env) -> None:
    started = _events((await _create(env)).text)[0]
    env.llm.fail = True

    response = await env.client.post(
        f"/api/side-questions/{started['side_question_id']}/messages", json={"content": "続き"}
    )

    assert _events(response.text)[-1]["type"] == "error"
    thread = (await env.client.get(f"/api/dialogue-sessions/{env.session_id}/side-questions")).json()[
        "side_questions"
    ][0]
    assert [m["content"] for m in thread["messages"]] == ["索引とは？", "索引は行の位置を指す一覧です"]


async def test_anchor_message_deleted_during_stream_emits_error_and_leaves_no_rows(env: Env) -> None:
    async def delete_anchor() -> None:
        async with env.pool.acquire() as conn:
            await dialogue_message_repository.delete_last_n(conn, env.session_id, 1)

    env.llm.during = delete_anchor

    response = await _create(env)

    assert response.status_code == 200
    events = _events(response.text)
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "side_question_anchor_gone"
    assert await _count(env, "side_questions") == 0
    assert await _count(env, "side_question_messages") == 0


async def test_get_returns_threads_with_messages(env: Env) -> None:
    await _create(env)
    await _create(env, quote="速く", occurrence=0, content="なぜ速い？")

    response = await env.client.get(f"/api/dialogue-sessions/{env.session_id}/side-questions")

    assert response.status_code == 200
    threads = response.json()["side_questions"]
    assert [t["quote"] for t in threads] == ["索引", "速く"]
    assert all(len(t["messages"]) == 2 for t in threads)
    assert "索引は行の位置を指す一覧です" in str(env.llm.calls[1][0].content)


async def test_get_of_unknown_session_is_not_found(env: Env) -> None:
    response = await env.client.get(f"/api/dialogue-sessions/{uuid4()}/side-questions")

    assert response.status_code == 404
