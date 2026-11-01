import uuid
from collections.abc import AsyncGenerator
from datetime import date, datetime
from typing import Any

import asyncpg
import pytest
import pytest_asyncio
from langchain_core.messages import BaseMessage
from pydantic import ValidationError

from core import config
from graph.output_schemas import ReflectionScriptOutput
from repositories import dialogue_session_repository, note_repository
from services import reflection_generation
from services.reflection_generation import (
    ReflectionEmptyError,
    ReflectionGenerationError,
    ReflectionLimitError,
    get_or_create_script,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

NOV_1 = date(2026, 11, 1)


class _FakeRunnable:
    def __init__(self, owner: "_FakeLLM") -> None:
        self.owner = owner

    async def ainvoke(self, messages: list[BaseMessage], config: dict[str, Any] | None = None) -> Any:
        self.owner.prompts.append(str(messages[0].content))
        self.owner.configs.append(config or {})
        if self.owner.fail:
            raise RuntimeError("boom")
        return ReflectionScriptOutput(sentences=self.owner.sentences)


class _FakeLLM:
    def __init__(self, *, fail: bool = False) -> None:
        self.sentences = ["あなたは今日二分探索を学習しました。", "半分に絞る考え方でした。"]
        self.fail = fail
        self.prompts: list[str] = []
        self.configs: list[dict[str, Any]] = []
        self.tasks: list[str] = []

    def with_structured_output(self, schema: type, *, task: str) -> _FakeRunnable:
        assert schema is ReflectionScriptOutput
        self.tasks.append(task)
        return _FakeRunnable(self)


@pytest_asyncio.fixture(loop_scope="session", autouse=True)
async def _use_test_pool(test_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None]:
    async def fake_get_pool() -> asyncpg.Pool:
        return test_pool

    monkeypatch.setattr(reflection_generation, "get_pool", fake_get_pool)
    yield


@pytest.fixture
def llm(monkeypatch: pytest.MonkeyPatch) -> _FakeLLM:
    fake = _FakeLLM()
    monkeypatch.setattr(reflection_generation, "llm_structured", fake)
    return fake


async def _finished_session(conn: asyncpg.Connection, user_id: str, topic: str = "二分探索") -> None:
    session_id = uuid.uuid4()
    note_id = uuid.uuid4()
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
        datetime.fromisoformat("2026-11-01T03:00:00Z"),
    )


async def _usage_count(conn: asyncpg.Connection) -> int:
    return int(await conn.fetchval("SELECT COUNT(*) FROM llm_usages WHERE operation = 'reflection_script'"))


async def test_second_call_uses_cache_without_reserving(
    db_conn: asyncpg.Connection, test_user: dict[str, str], llm: _FakeLLM
) -> None:
    user_id = test_user["id"]
    await _finished_session(db_conn, user_id)

    first = await get_or_create_script(user_id, "day", NOV_1)
    second = await get_or_create_script(user_id, "day", NOV_1)

    assert first == second == llm.sentences
    assert len(llm.prompts) == 1
    assert llm.tasks == ["generate-reflection-script"]
    assert "二分探索" in llm.prompts[0]
    assert "prompt_fingerprint" in llm.configs[0]["metadata"]
    assert await _usage_count(db_conn) == 1


async def test_regenerates_when_content_changes(
    db_conn: asyncpg.Connection, test_user: dict[str, str], llm: _FakeLLM
) -> None:
    user_id = test_user["id"]
    await _finished_session(db_conn, user_id)
    await get_or_create_script(user_id, "day", NOV_1)

    await _finished_session(db_conn, user_id, topic="ハッシュ表")
    await get_or_create_script(user_id, "day", NOV_1)

    assert len(llm.prompts) == 2
    assert "ハッシュ表" in llm.prompts[1]
    assert await _usage_count(db_conn) == 2


async def test_week_uses_week_start_and_opening(
    db_conn: asyncpg.Connection, test_user: dict[str, str], llm: _FakeLLM
) -> None:
    user_id = test_user["id"]
    await _finished_session(db_conn, user_id)

    await get_or_create_script(user_id, "week", NOV_1)

    assert "今週" in llm.prompts[0]
    row = await db_conn.fetchrow("SELECT start_date FROM reflection_generations WHERE user_id = $1", user_id)
    assert row is not None
    assert row["start_date"] == date(2026, 10, 26)


async def test_empty_day_raises_before_reserving(
    db_conn: asyncpg.Connection, test_user: dict[str, str], llm: _FakeLLM
) -> None:
    with pytest.raises(ReflectionEmptyError):
        await get_or_create_script(test_user["id"], "day", NOV_1)

    assert await _usage_count(db_conn) == 0
    assert llm.prompts == []


async def test_llm_failure_keeps_reservation(
    db_conn: asyncpg.Connection, test_user: dict[str, str], llm: _FakeLLM
) -> None:
    user_id = test_user["id"]
    await _finished_session(db_conn, user_id)
    llm.fail = True

    with pytest.raises(ReflectionGenerationError):
        await get_or_create_script(user_id, "day", NOV_1)

    assert await _usage_count(db_conn) == 1
    assert await db_conn.fetchval("SELECT COUNT(*) FROM reflection_generations") == 0


async def test_limit_reached_raises(
    db_conn: asyncpg.Connection, test_user: dict[str, str], llm: _FakeLLM, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = test_user["id"]
    await _finished_session(db_conn, user_id)
    monkeypatch.setattr(config, "DAILY_REFLECTION_GENERATION_LIMIT", 0)

    with pytest.raises(ReflectionLimitError):
        await get_or_create_script(user_id, "day", NOV_1)

    assert llm.prompts == []


async def test_script_output_rejects_long_sentence() -> None:
    with pytest.raises(ValidationError):
        ReflectionScriptOutput(sentences=["あ" * 501])


async def test_script_output_rejects_long_total_and_empty() -> None:
    with pytest.raises(ValidationError):
        ReflectionScriptOutput(sentences=["あ" * 300] * 4)
    with pytest.raises(ValidationError):
        ReflectionScriptOutput(sentences=[])
