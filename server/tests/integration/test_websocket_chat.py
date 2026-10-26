import asyncio
import json
import os
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, RemoveMessage

from api.websocket import auth as ws_auth
from api.websocket import chat
from core import config as app_config
from core.terms import TERMS_VERSION
from graph.version import GRAPH_VERSION
from repositories import (
    dialogue_message_repository,
    dialogue_session_repository,
    study_memo_repository,
    user_consent_repository,
)
from schemas.websocket_message import MAX_MESSAGE_CONTENT_LENGTH, PROTOCOL_VERSION
from services.transcription_keywords import KeywordSource

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://curigor:localdev@localhost:5433/curigor_test",
)


class FakeGraph:
    """LangGraph のコンパイル済みグラフを模した最小スタブ。

    LLM / チェックポイントへの実通信を遮断しつつ、chat.py が依存する
    astream / ainvoke / aget_state / aupdate_state だけを提供する。
    """

    def __init__(self) -> None:
        self.stream_chunks: list[tuple[str, str]] = [("こんにちは", "learning_start")]
        self.state_values: dict[str, Any] = {"should_generate_note": False, "turn_count": 1}
        self.ainvoke_result: dict[str, Any] = {}
        self.update_calls: list[tuple[dict[str, Any], str | None]] = []
        self.stream_inputs: list[Any] = []

    async def astream(
        self, graph_input: Any, config: Any, stream_mode: str = "messages"
    ) -> AsyncIterator[tuple[AIMessageChunk, dict[str, Any]]]:
        self.stream_inputs.append(graph_input)
        for content, node in self.stream_chunks:
            yield AIMessageChunk(content=content), {"langgraph_node": node}

    async def ainvoke(self, graph_input: Any, config: Any = None) -> dict[str, Any]:
        return self.ainvoke_result

    async def aget_state(self, config: Any) -> SimpleNamespace:
        return SimpleNamespace(values=self.state_values)

    async def aget_state_history(self, config: Any) -> AsyncIterator[SimpleNamespace]:
        return
        yield

    async def aupdate_state(self, config: Any, values: dict[str, Any], as_node: str | None = None) -> None:
        self.update_calls.append((dict(values), as_node))


class FakeWebSocket:
    """切断経路を決定的に検証するための WebSocket スタブ。

    inbound を順に返し、尽きたら WebSocketDisconnect を送出する。
    """

    def __init__(self, graph: FakeGraph, inbound: list[str]) -> None:
        self.app = SimpleNamespace(state=SimpleNamespace(graph=graph))
        self._inbound = list(inbound)
        self.sent: list[str] = []

    async def accept(self) -> None:
        return None

    async def receive_text(self) -> str:
        if self._inbound:
            return self._inbound.pop(0)
        raise WebSocketDisconnect(code=1005)

    async def send_text(self, data: str) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        return None


# -----------------------------------------------------------
# DB ヘルパー（TestClient 独自ループと衝突しないよう毎回新規接続）
# -----------------------------------------------------------


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _setup_user(user_id: str) -> None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute(
            'INSERT INTO "user" (id, name, email, "emailVerified") '
            "VALUES ($1, $2, $3, true) ON CONFLICT (id) DO NOTHING",
            user_id,
            "WS Test",
            f"{user_id}@example.com",
        )
        await user_consent_repository.record(conn, user_id, TERMS_VERSION)
    finally:
        await conn.close()


async def _truncate() -> None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute(
            "TRUNCATE llm_usages, feedbacks, review_schedules, dialogue_messages, dialogue_sessions, notes, "
            "note_collections CASCADE"
        )
    finally:
        await conn.close()


async def _insert_session(session_id: UUID, user_id: str, graph_version: int) -> None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute(
            "INSERT INTO dialogue_sessions (id, user_id, session_type, status, graph_version) "
            "VALUES ($1, $2, 'learning', 'in_progress', $3)",
            str(session_id),
            user_id,
            graph_version,
        )
    finally:
        await conn.close()


async def _set_session_type(session_id: UUID, session_type: str) -> None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute(
            "UPDATE dialogue_sessions SET session_type = $2 WHERE id = $1", str(session_id), session_type
        )
    finally:
        await conn.close()


async def _insert_note(user_id: str, topic: str = "統計学", aspect_map: str | None = None) -> UUID:
    note_id = uuid4()
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute(
            "INSERT INTO notes (id, user_id, topic, content, summary, status, aspect_map) "
            "VALUES ($1, $2, $3, 'content', 'summary', 'active', $4::jsonb)",
            str(note_id),
            user_id,
            topic,
            aspect_map,
        )
    finally:
        await conn.close()
    return note_id


async def _insert_feedback(note_id: UUID, user_id: str, improvements: str, items: list[dict[str, Any]]) -> UUID:
    feedback_id = uuid4()
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        session_id = uuid4()
        await conn.execute(
            "INSERT INTO dialogue_sessions (id, user_id, session_type, status)"
            " VALUES ($1, $2, 'learning', 'completed')",
            session_id,
            user_id,
        )
        await conn.execute(
            "INSERT INTO feedbacks (id, note_id, dialogue_session_id, understanding_level, strength, improvements,"
            " improvement_items) VALUES ($5, $1, $2, 'low', 's', $3, $4::jsonb)",
            note_id,
            session_id,
            improvements,
            json.dumps(items, ensure_ascii=False),
            feedback_id,
        )
    finally:
        await conn.close()
    return feedback_id


async def _insert_review_session(session_id: UUID, user_id: str, note_id: UUID, graph_version: int) -> None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute(
            "INSERT INTO dialogue_sessions (id, user_id, session_type, status, graph_version, note_id) "
            "VALUES ($1, $2, 'review', 'in_progress', $3, $4)",
            str(session_id),
            user_id,
            graph_version,
            str(note_id),
        )
    finally:
        await conn.close()


async def _insert_messages(session_id: UUID, rows: list[tuple[str, str]]) -> None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        for order, (role, content) in enumerate(rows, start=1):
            await conn.execute(
                "INSERT INTO dialogue_messages (id, dialogue_session_id, role, content, message_order) "
                "VALUES (gen_random_uuid(), $1, $2, $3, $4)",
                str(session_id),
                role,
                content,
                order,
            )
    finally:
        await conn.close()


async def _insert_messages_after(session_id: UUID, order: int, role: str, content: str) -> None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute(
            "INSERT INTO dialogue_messages (id, dialogue_session_id, role, content, message_order) "
            "VALUES (gen_random_uuid(), $1, $2, $3, $4)",
            str(session_id),
            role,
            content,
            order,
        )
    finally:
        await conn.close()


async def _insert_topic_edit_after(session_id: UUID, order: int, topic: str) -> None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute(
            "INSERT INTO dialogue_messages (id, dialogue_session_id, role, content, message_order, topic_edit) "
            "VALUES (gen_random_uuid(), $1, 'user', $2, $3, $4)",
            str(session_id),
            f"トピックを「{topic}」に変更しました",
            order,
            topic,
        )
    finally:
        await conn.close()


async def _fetch_messages(session_id: UUID) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        return await conn.fetch(
            "SELECT role, content, message_order, intake_card, intake_answers, "
            "topic_correction_card, topic_correction_answer, topic_edit FROM dialogue_messages "
            "WHERE dialogue_session_id = $1 ORDER BY message_order",
            str(session_id),
        )
    finally:
        await conn.close()


async def _fetch_user_input_modes(session_id: UUID) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        return await conn.fetch(
            "SELECT content, input_mode, raw_transcript FROM dialogue_messages "
            "WHERE dialogue_session_id = $1 AND role = 'user' ORDER BY message_order",
            str(session_id),
        )
    finally:
        await conn.close()


async def _fetch_session(session_id: UUID) -> asyncpg.Record | None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        return await conn.fetchrow("SELECT * FROM dialogue_sessions WHERE id = $1", str(session_id))
    finally:
        await conn.close()


# -----------------------------------------------------------
# fixtures
# -----------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_plan_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    async def none(note_id: UUID, user_id: str) -> None:
        return None

    monkeypatch.setattr(chat, "generate_review_plan", none)


@pytest.fixture
def ws_env(_run_migrations: None, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    user_id = "ws-test-user"
    _run(_setup_user(user_id))
    _run(_truncate())

    holder: dict[str, asyncpg.Pool | None] = {"pool": None}

    async def fake_get_pool() -> asyncpg.Pool:
        pool = holder["pool"]
        if pool is None:
            pool = await asyncpg.create_pool(TEST_DATABASE_URL)
            holder["pool"] = pool
        return pool

    monkeypatch.setattr(chat, "get_pool", fake_get_pool)
    monkeypatch.setattr(ws_auth, "verify_jwt", lambda token: {"sub": user_id})

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        if holder["pool"] is not None:
            await holder["pool"].close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(chat.router)
    fake_graph = FakeGraph()
    app.state.graph = fake_graph

    return SimpleNamespace(app=app, graph=fake_graph, user_id=user_id)


# -----------------------------------------------------------
# WebSocket ヘルパー
# -----------------------------------------------------------


_MAP_WITH_CONTENT = {
    "session_type": "learning",
    "should_generate_note": False,
    "turn_count": 3,
    "depth_map": {"aspects": []},
    "map_covered": [{"aspect_id": "a1", "reached_stage": "defined"}],
}


def _send(ws: Any, content: str) -> None:
    ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": content})


async def _session_status(session_id: UUID) -> str:
    session = await _fetch_session(session_id)
    assert session is not None
    return str(session["status"])


def _authenticate(ws: Any) -> None:
    ws.send_json({"type": "authenticate", "token": "x", "protocol_version": PROTOCOL_VERSION})


def _start_learning(ws: Any, topic: str = "二分探索") -> str:
    """start_learning を送り、session_started〜assistant_message_end を消費して session_id を返す。"""
    ws.send_json({"type": "start_learning", "topic": topic})
    started = ws.receive_json()
    assert started["type"] == "session_started"
    assert ws.receive_json()["type"] == "assistant_message_chunk"
    assert ws.receive_json()["type"] == "assistant_message_end"
    return str(started["session_id"])


def _resume_and_collect(ws_env: SimpleNamespace, session_id: UUID) -> list[dict[str, Any]]:
    """resume を送り、session_ended までに届いたメッセージを順に返す。

    特定の型を receive_json で待ち伏せると、送られなくなった回帰でテストが固まる（落ちない）。
    """
    received: list[dict[str, Any]] = []
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "resume_session", "session_id": str(session_id)})
        ws.send_json({"type": "end_session"})
        while True:
            message = ws.receive_json()
            received.append(message)
            if message["type"] in ("session_ended", "error"):
                return received


def _wait_until_handled(ws: Any) -> None:
    """直前のメッセージの処理（応答の保存まで）が終わるのを待つ。サーバーはメッセージを順に処理する。"""
    ws.send_json({"type": "unknown"})
    assert ws.receive_json()["type"] == "error"


def _drain_assistant_turn(ws: Any) -> None:
    assert ws.receive_json()["type"] == "assistant_message_chunk"
    assert ws.receive_json()["type"] == "assistant_message_end"


# -----------------------------------------------------------
# tests
# -----------------------------------------------------------


def test_start_learning_streams_assistant_message(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_learning", "topic": "二分探索"})

        assert ws.receive_json()["type"] == "session_started"
        chunk = ws.receive_json()
        assert chunk["type"] == "assistant_message_chunk"
        assert chunk["content"]
        assert ws.receive_json()["type"] == "assistant_message_end"


def test_trial_start_learning_sends_the_kickoff_and_marks_the_session(ws_env: SimpleNamespace) -> None:
    ws_env.graph.stream_chunks = []
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 1,
        "topic": "虹が見える理由",
        "messages": [
            HumanMessage(content="虹が見える理由"),
            AIMessage(content="お試しの声かけ", additional_kwargs={"trial_kickoff": True}),
        ],
    }
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_learning", "topic": "虹が見える理由", "trial": True})
        started = ws.receive_json()
        assert started["type"] == "session_started"
        chunk = ws.receive_json()
        assert chunk == {"type": "assistant_message_chunk", "content": "お試しの声かけ"}
        assert ws.receive_json()["type"] == "assistant_message_end"

    session_id = UUID(started["session_id"])
    assert ws_env.graph.stream_inputs[0]["trial"] is True
    session = _run(_fetch_session(session_id))
    assert session is not None
    assert session["is_trial"] is True
    assert session["topic"] == "虹が見える理由"
    messages = _run(_fetch_messages(session_id))
    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "虹が見える理由"),
        ("assistant", "お試しの声かけ"),
    ]


def test_regular_start_learning_is_not_a_trial(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = UUID(_start_learning(ws))

    assert "trial" not in ws_env.graph.stream_inputs[0]
    session = _run(_fetch_session(session_id))
    assert session is not None
    assert session["is_trial"] is False


def test_start_learning_by_voice_stores_the_raw_transcript(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_learning", "topic": "二分探索", "raw_transcript": "にぶんたんさく"})
        started = ws.receive_json()
        assert started["type"] == "session_started"
        _drain_assistant_turn(ws)

    rows = _run(_fetch_user_input_modes(UUID(started["session_id"])))
    assert [(r["content"], r["input_mode"], r["raw_transcript"]) for r in rows] == [
        ("二分探索", "voice", "にぶんたんさく"),
    ]


def test_start_learning_by_typing_stays_text_input(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = UUID(_start_learning(ws))

    rows = _run(_fetch_user_input_modes(session_id))
    assert [(r["content"], r["input_mode"], r["raw_transcript"]) for r in rows] == [("二分探索", "text", None)]


def test_start_learning_auto_sent_by_voice_is_stored_as_voice_auto(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json(
            {"type": "start_learning", "topic": "二分探索", "raw_transcript": "にぶんたんさく", "auto_sent": True}
        )
        started = ws.receive_json()
        assert started["type"] == "session_started"
        _drain_assistant_turn(ws)

    rows = _run(_fetch_user_input_modes(UUID(started["session_id"])))
    assert [(r["input_mode"], r["raw_transcript"]) for r in rows] == [("voice_auto", "にぶんたんさく")]


def test_user_message_auto_sent_by_voice_is_stored_as_voice_auto(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = UUID(_start_learning(ws))
        ws.send_json(
            {
                "type": "user_message",
                "content": "半分に絞ります",
                "client_message_id": str(uuid4()),
                "raw_transcript": "はんぶんにしぼります",
                "auto_sent": True,
            }
        )
        _drain_assistant_turn(ws)

    rows = _run(_fetch_user_input_modes(session_id))
    assert (rows[-1]["content"], rows[-1]["input_mode"]) == ("半分に絞ります", "voice_auto")


async def _fetch_user_stt_fields(session_id: UUID) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        return await conn.fetch(
            "SELECT stt_method, stt_latency_ms FROM dialogue_messages "
            "WHERE dialogue_session_id = $1 AND role = 'user' ORDER BY message_order",
            str(session_id),
        )
    finally:
        await conn.close()


def test_voice_conversation_messages_store_the_stt_method_and_latency(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json(
            {
                "type": "start_learning",
                "topic": "二分探索",
                "raw_transcript": "二分探索",
                "auto_sent": True,
                "stt_method": "segmented",
                "stt_latency_ms": 640,
            }
        )
        started = ws.receive_json()
        _drain_assistant_turn(ws)
        ws.send_json(
            {
                "type": "user_message",
                "content": "半分に絞ります",
                "client_message_id": str(uuid4()),
                "raw_transcript": "半分に絞ります",
                "auto_sent": True,
                "stt_method": "segmented",
                "stt_latency_ms": 910,
            }
        )
        _drain_assistant_turn(ws)

    rows = _run(_fetch_user_stt_fields(UUID(started["session_id"])))
    assert [(r["stt_method"], r["stt_latency_ms"]) for r in rows] == [("segmented", 640), ("segmented", 910)]


def test_start_review_without_note_returns_error(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_review", "note_id": str(uuid4())})

        err = ws.receive_json()
        assert err["type"] == "error"
        assert "ノートが見つかりません" in err["detail"]


def test_user_message_without_session_returns_error(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "こんにちは"})

        err = ws.receive_json()
        assert err["type"] == "error"
        assert "セッションが開始されていません。ページを再読み込みしてください" in err["detail"]


def test_user_message_streams_assistant_message(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)

        ws.send_json(
            {"type": "user_message", "client_message_id": str(uuid4()), "content": "二分探索は半分に絞る手法です"}
        )
        _drain_assistant_turn(ws)


def test_assistant_message_end_carries_learning_progress(ws_env: SimpleNamespace) -> None:
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 3,
        "covered_aspects": [
            {"aspect": "計算量", "reached_depth": "exemplified"},
            {"aspect": "前提条件", "reached_depth": "defined"},
        ],
    }
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)

        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "計算量は O(log n)"})
        assert ws.receive_json()["type"] == "assistant_message_chunk"
        end = ws.receive_json()

    assert end == {
        "type": "assistant_message_end",
        "topic": None,
        "end_confirmation": None,
        "note_peek_available": False,
        "progress": {
            "reached_aspects": ["計算量"],
            "target_count": 3,
            "is_complete": False,
            "aspects": [],
            "intake": None,
        },
    }


async def _session_topic(session_id: str) -> str | None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        return cast("str | None", await conn.fetchval("SELECT topic FROM dialogue_sessions WHERE id = $1", session_id))
    finally:
        await conn.close()


def test_user_message_saves_and_announces_a_topic_the_graph_changed(
    ws_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    updates: list[str] = []
    original = dialogue_session_repository.update_topic

    async def counting_update_topic(conn: Any, session_id: UUID, topic: str) -> None:
        updates.append(topic)
        await original(conn, session_id, topic)

    monkeypatch.setattr(dialogue_session_repository, "update_topic", counting_update_topic)
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = _start_learning(ws, topic="この仕組みを学びたい")
        ws_env.graph.state_values = {"should_generate_note": False, "turn_count": 2, "topic": "Linuxの仕組み"}

        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "Linuxの仕組みです"})
        assert ws.receive_json()["type"] == "assistant_message_chunk"
        first_end = ws.receive_json()
        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "続きです"})
        assert ws.receive_json()["type"] == "assistant_message_chunk"
        ws.receive_json()

    assert first_end["topic"] == "Linuxの仕組み"
    assert _run(_session_topic(session_id)) == "Linuxの仕組み"
    assert updates == ["Linuxの仕組み"]


_FOCUS_MAP = {
    "root": "統計学",
    "aspects": [
        {"name": "計算量", "summary": "", "coverage": "covered", "children": []},
        {"name": "前提条件", "summary": "", "coverage": "partial", "children": []},
    ],
}
_FOCUS_ITEMS: list[dict[str, Any]] = [
    {"text": "計算量の見積もり", "aspect_id": "a1"},
    {"text": "ソート済みの前提", "aspect_id": "a2"},
    {"text": "用語の使い分け", "aspect_id": None},
]


def _plan_point(point_id: str, source: str, aspect_id: str | None = None) -> dict[str, Any]:
    return {
        "id": point_id,
        "point": f"要点{point_id}",
        "question": f"質問{point_id}",
        "expected": ["期待"],
        "source": source,
        "aspect_id": aspect_id,
        "in_note": True,
    }


async def _insert_plan(note_id: UUID, points: list[dict[str, Any]]) -> None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute(
            "INSERT INTO review_plans (note_id, points, note_content_hash, prompt_fingerprint)"
            " VALUES ($1, $2::jsonb, 'h', 'f')",
            note_id,
            json.dumps(points, ensure_ascii=False),
        )
    finally:
        await conn.close()


def _start_review_with_plan(
    ws_env: SimpleNamespace, points: list[dict[str, Any]] | None, **message: Any
) -> dict[str, Any]:
    note_id = _run(_insert_note(ws_env.user_id, aspect_map=json.dumps(_FOCUS_MAP)))
    _run(_insert_feedback(note_id, ws_env.user_id, "\n".join(i["text"] for i in _FOCUS_ITEMS), _FOCUS_ITEMS))
    if points is not None:
        _run(_insert_plan(note_id, points))
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_review", "note_id": str(note_id), **message})
        assert ws.receive_json()["type"] == "session_started"
        ws.receive_json()
        ws.receive_json()
    state: dict[str, Any] = ws_env.graph.stream_inputs[0]
    return state


def test_start_review_loads_the_saved_plan_in_priority_order(ws_env: SimpleNamespace) -> None:
    points = [
        _plan_point("p1", "general"),
        _plan_point("p2", "carryover"),
        _plan_point("p3", "aspect_gap", "a2"),
    ]

    initial = _start_review_with_plan(ws_env, points)

    assert [p["id"] for p in initial["review_points"]] == ["p2", "p1", "p3"]
    assert all(p["status"] == "pending" for p in initial["review_points"])
    assert initial["review_current_point_id"] is None
    assert initial["wrap_up_offered"] is False
    assert "prior_improvements" not in initial


def test_start_review_generates_a_plan_when_missing(ws_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    generated = [_plan_point("g1", "general")]

    async def fake_generate(note_id: UUID, user_id: str) -> list[Any]:
        return generated

    monkeypatch.setattr(chat, "generate_review_plan", fake_generate)

    initial = _start_review_with_plan(ws_env, None)

    assert [p["id"] for p in initial["review_points"]] == ["g1"]
    assert "prior_improvements" not in initial


def test_start_review_falls_back_when_plan_generation_times_out(
    ws_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def slow_generate(note_id: UUID, user_id: str) -> list[Any]:
        await asyncio.sleep(5)
        return [_plan_point("g1", "general")]

    monkeypatch.setattr(chat, "generate_review_plan", slow_generate)
    monkeypatch.setattr(app_config, "REVIEW_PLAN_SYNC_TIMEOUT_SECONDS", 0.05)

    initial = _start_review_with_plan(ws_env, None)

    assert "review_points" not in initial
    assert initial["prior_improvements"]


async def test_plan_generation_that_times_out_still_finishes_in_the_background(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[UUID] = []

    async def slow_generate(note_id: UUID, user_id: str) -> list[Any]:
        await asyncio.sleep(0.1)
        saved.append(note_id)
        return [_plan_point("g1", "general")]

    monkeypatch.setattr(chat, "generate_review_plan", slow_generate)
    monkeypatch.setattr(app_config, "REVIEW_PLAN_SYNC_TIMEOUT_SECONDS", 0.01)
    note_id = uuid4()

    assert await chat._generate_plan_within_timeout(note_id, "user") is None
    assert saved == []
    await asyncio.gather(*chat._background_plans)
    assert saved == [note_id]
    assert not chat._background_plans


async def test_plan_generation_failure_in_the_background_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_generate(note_id: UUID, user_id: str) -> list[Any]:
        await asyncio.sleep(0.05)
        raise RuntimeError("boom")

    monkeypatch.setattr(chat, "generate_review_plan", failing_generate)
    monkeypatch.setattr(app_config, "REVIEW_PLAN_SYNC_TIMEOUT_SECONDS", 0.01)

    assert await chat._generate_plan_within_timeout(uuid4(), "user") is None
    results = await asyncio.gather(*chat._background_plans, return_exceptions=True)
    assert [type(r) for r in results] == [RuntimeError]


def test_start_review_with_an_empty_plan_falls_back(ws_env: SimpleNamespace) -> None:
    initial = _start_review_with_plan(ws_env, [])

    assert "review_points" not in initial
    assert initial["prior_improvements"] == "計算量の見積もり\nソート済みの前提\n用語の使い分け"


def test_start_review_cannot_read_another_users_plan(ws_env: SimpleNamespace) -> None:
    other = "other-user"
    _run(_setup_user(other))
    note_id = _run(_insert_note(other))
    _run(_insert_plan(note_id, [_plan_point("p1", "general")]))

    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_review", "note_id": str(note_id)})
        assert ws.receive_json()["code"] == "note_not_found"
    assert ws_env.graph.stream_inputs == []


async def _undo_with(
    before: dict[str, Any], after: dict[str, Any], human: HumanMessage, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Any]:
    checkpoint: dict[str, Any] = {"cp": 1}

    class Graph:
        def __init__(self) -> None:
            self.updates: list[dict[str, Any]] = []

        async def aget_state(self, config: Any) -> SimpleNamespace:
            return SimpleNamespace(values=before if config is checkpoint else after)

        async def aupdate_state(self, config: Any, values: dict[str, Any]) -> None:
            self.updates.append(values)

    async def clear_turn(conn: Any, session_id: Any) -> None:
        return None

    monkeypatch.setattr(dialogue_session_repository, "clear_turn", clear_turn)
    graph = Graph()
    deps = SimpleNamespace(graph=graph, pool=_NullPool())
    ctx = SimpleNamespace(config={"cfg": 1}, session_id=uuid4(), is_taken_over=False)

    await chat._undo_taken_over_turn(human, checkpoint, ctx, deps)  # type: ignore[arg-type]

    [update] = graph.updates
    return update


async def test_undo_taken_over_turn_restores_review_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    before = {
        "messages": [],
        "turn_count": 1,
        "review_points": [{"id": "p1", "status": "pending"}],
        "review_current_point_id": None,
        "wrap_up_offered": False,
        "map_covered": [],
    }
    human = HumanMessage(content="x", id="h1")
    after = {
        **before,
        "messages": [human, AIMessage(content="y", id="a1")],
        "turn_count": 2,
        "review_points": [{"id": "p1", "status": "explained"}],
        "review_current_point_id": "p1",
        "wrap_up_offered": True,
        "map_covered": [{"aspect_id": "a1", "reached_stage": "defined"}],
    }

    update = await _undo_with(before, after, human, monkeypatch)

    assert update["review_points"] == before["review_points"]
    assert update["review_current_point_id"] is None
    assert update["wrap_up_offered"] is False
    assert update["map_covered"] == []


async def test_undo_taken_over_turn_clears_keys_the_turn_first_set(monkeypatch: pytest.MonkeyPatch) -> None:
    human = HumanMessage(content="x", id="h1")
    before = {"messages": [human], "turn_count": 1}
    after = {
        **before,
        "messages": [human, AIMessage(content="y", id="a1")],
        "turn_count": 2,
        "end_confirmation": "offered",
        "review_answered": True,
    }

    update = await _undo_with(before, after, human, monkeypatch)

    assert update["turn_count"] == 1
    assert update["end_confirmation"] is None
    assert update["review_answered"] is None


class _HistoryGraph:
    def __init__(self, current: dict[str, Any], history: list[dict[str, Any]]) -> None:
        self.current = current
        self.history = history
        self.updates: list[dict[str, Any]] = []

    async def aget_state(self, config: Any) -> SimpleNamespace:
        return SimpleNamespace(values=self.current)

    async def aget_state_history(self, config: Any) -> AsyncIterator[SimpleNamespace]:
        for values in self.history:
            yield SimpleNamespace(values=values)

    async def aupdate_state(self, config: Any, values: dict[str, Any]) -> None:
        self.updates.append(values)
        self.current = {**self.current, **{k: v for k, v in values.items() if k != "messages"}}


class _NullPool:
    def acquire(self) -> Any:
        @asynccontextmanager
        async def ctx() -> AsyncIterator[None]:
            yield None

        return ctx()


class _SentTexts:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_text(self, data: str) -> None:
        self.sent.append(data)


async def _cancel_with(graph: Any, monkeypatch: pytest.MonkeyPatch, session_type: str = "learning") -> SimpleNamespace:
    async def delete_last_n(conn: Any, session_id: Any, n: int) -> None:
        return None

    monkeypatch.setattr(dialogue_message_repository, "delete_last_n", delete_last_n)
    deps = SimpleNamespace(graph=graph, pool=_NullPool(), websocket=_SentTexts())
    ctx = SimpleNamespace(config={"cfg": 1}, session_id=uuid4(), message_order=6, session_type=session_type)
    await chat._handle_cancel_last_message(ctx, deps)  # type: ignore[arg-type]
    return deps


async def test_cancel_restores_review_progress_from_before_the_cancelled_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    earlier = [
        HumanMessage(content="ノート", id="h0"),
        AIMessage(content="覚えていることは？", id="a0"),
        HumanMessage(content="答え", id="h1"),
        AIMessage(content="p1 の質問", id="a1"),
    ]
    cancelled = [HumanMessage(content="p1 の答え", id="h2"), AIMessage(content="p2 の質問", id="a2")]

    def progress(messages: list[Any], status: str, current: str | None, offered: bool) -> dict[str, Any]:
        return {
            "messages": messages,
            "turn_count": 2,
            "review_points": [{"id": "p1", "status": status}, {"id": "p2", "status": "pending"}],
            "review_current_point_id": current,
            "wrap_up_offered": offered,
        }

    after = progress([*earlier, *cancelled], "explained", "p2", True)
    with_human = progress([*earlier, cancelled[0]], "pending", "p1", False)
    before = progress(earlier, "pending", "p1", False)
    older = progress(earlier[:2], "pending", None, False)
    graph = _HistoryGraph(after, [after, with_human, before, older])

    deps = await _cancel_with(graph, monkeypatch)

    assert json.loads(deps.websocket.sent[-1])["type"] == "cancel_last_message_success"
    [update] = graph.updates
    assert [m.id for m in update["messages"]] == ["a2", "h2"]
    assert update["review_points"] == before["review_points"]
    assert update["review_current_point_id"] == "p1"
    assert update["wrap_up_offered"] is False


def _cancel_turn(
    before_extra: dict[str, Any], after_extra: dict[str, Any]
) -> tuple[_HistoryGraph, dict[str, Any], dict[str, Any]]:
    earlier = [HumanMessage(content="t", id="h0"), AIMessage(content="q", id="a0")]
    cancelled = [HumanMessage(content="答え", id="h1"), AIMessage(content="次", id="a1")]
    before = {"messages": earlier, "turn_count": 1, **before_extra}
    after = {**before, "messages": [*earlier, *cancelled], "turn_count": 2, **after_extra}
    graph = _HistoryGraph(after, [after, {**before, "messages": [*earlier, cancelled[0]]}, before])
    return graph, before, after


async def test_cancel_rewinds_learning_progress_to_before_the_cancelled_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph, _, _ = _cancel_turn(
        {
            "map_covered": [],
            "covered_aspects": [],
            "wrap_up_offered": False,
            "turn_analysis": {"response_mode": "probe"},
        },
        {
            "map_covered": [{"aspect_id": "a1", "reached_stage": "defined"}],
            "covered_aspects": [{"aspect": "x", "reached_depth": "mentioned"}],
            "wrap_up_offered": True,
            "turn_analysis": {"response_mode": "wrap_up"},
            "end_confirmation": "offered",
        },
    )

    await _cancel_with(graph, monkeypatch)

    [update] = graph.updates
    assert [m.id for m in update["messages"]] == ["a1", "h1"]
    assert update["turn_count"] == 1
    assert update["map_covered"] == []
    assert update["covered_aspects"] == []
    assert update["wrap_up_offered"] is False
    assert update["turn_analysis"] == {"response_mode": "probe"}
    assert update["end_confirmation"] is None
    assert update["pending_topic_correction"] is None


class _RewindingGraph(_HistoryGraph):
    async def aupdate_state(self, config: Any, values: dict[str, Any]) -> None:
        await super().aupdate_state(config, values)
        self.current = {**self.current, **{k: v for k, v in values.items() if k != "messages"}}


async def test_cancel_success_carries_the_rewound_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    depth_map = {"aspects": [{"id": "a1", "name": "観点1", "is_core": True}]}
    graph, _, _ = _cancel_turn(
        {"depth_map": depth_map, "map_covered": []},
        {"depth_map": depth_map, "map_covered": [{"aspect_id": "a1", "reached_stage": "defined"}]},
    )
    rewinding = _RewindingGraph(graph.current, graph.history)

    deps = await _cancel_with(rewinding, monkeypatch)

    res = json.loads(deps.websocket.sent[-1])
    assert res["type"] == "cancel_last_message_success"
    assert res["progress"]["aspects"]
    assert all(a["reached_stage"] is None for a in res["progress"]["aspects"])


async def test_cancel_success_has_no_progress_outside_learning(monkeypatch: pytest.MonkeyPatch) -> None:
    graph, _, _ = _cancel_turn({}, {})

    deps = await _cancel_with(graph, monkeypatch, session_type="review")

    assert json.loads(deps.websocket.sent[-1])["progress"] is None


async def test_cancel_rewinds_explore_terms_and_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    graph, _, _ = _cancel_turn(
        {"explore_terms": [{"term": "A"}], "explore_questions": []},
        {"explore_terms": [{"term": "A"}, {"term": "B"}], "explore_questions": [{"question": "q"}]},
    )

    await _cancel_with(graph, monkeypatch)

    [update] = graph.updates
    assert update["explore_terms"] == [{"term": "A"}]
    assert update["explore_questions"] == []


async def test_cancel_rewinds_review_answered(monkeypatch: pytest.MonkeyPatch) -> None:
    graph, before, _ = _cancel_turn({}, {"review_answered": True})
    assert "review_answered" not in before

    await _cancel_with(graph, monkeypatch)

    [update] = graph.updates
    assert update["review_answered"] is None


async def test_cancel_without_a_matching_checkpoint_falls_back_to_messages_and_turn_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = {
        "messages": [
            HumanMessage(content="a", id="h0"),
            AIMessage(content="b", id="a0"),
            HumanMessage(content="c", id="h1"),
            AIMessage(content="d", id="a1"),
        ],
        "turn_count": 2,
        "wrap_up_offered": True,
    }
    graph = _HistoryGraph(current, [])

    await _cancel_with(graph, monkeypatch)

    [update] = graph.updates
    assert [m.id for m in update.pop("messages")] == ["a1", "h1"]
    assert update == {"turn_count": 1, "end_confirmation": None, "pending_topic_correction": None}


def _start_review_state(ws_env: SimpleNamespace, **message: Any) -> dict[str, Any]:
    note_id = _run(_insert_note(ws_env.user_id, aspect_map=json.dumps(_FOCUS_MAP)))
    _run(_insert_feedback(note_id, ws_env.user_id, "\n".join(i["text"] for i in _FOCUS_ITEMS), _FOCUS_ITEMS))
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_review", "note_id": str(note_id), **message})
        assert ws.receive_json()["type"] == "session_started"
        ws.receive_json()
        ws.receive_json()
    state: dict[str, Any] = ws_env.graph.stream_inputs[0]
    return state


def test_start_review_ignores_focus_from_older_clients(ws_env: SimpleNamespace) -> None:
    initial = _start_review_state(ws_env, focus_aspect_ids=["a1"])

    assert "review_points" not in initial
    assert initial["prior_improvements"] == "計算量の見積もり\nソート済みの前提\n用語の使い分け"


async def _insert_memo_from_feedback(user_id: str, note_id: UUID, feedback_id: UUID, aspect_id: str) -> None:
    session_id = uuid4()
    await _insert_session(session_id, user_id, graph_version=GRAPH_VERSION)
    await _set_session_type(session_id, "explore")
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await study_memo_repository.insert(
            conn,
            user_id=user_id,
            dialogue_session_id=session_id,
            topic="二分探索",
            source="",
            summary="",
            overview=[],
            glossary=[],
            questions=[],
            depth_map=_EXPLORE_MAP,
            origin={
                "note_id": str(note_id),
                "feedback_id": str(feedback_id),
                "improvement_index": 0,
                "improvement": "ソート済みの前提",
                "aspect_id": aspect_id,
            },
        )
    finally:
        await conn.close()


def _start_review_with_memo(ws_env: SimpleNamespace, *, memo_on_latest: bool) -> dict[str, Any]:
    note_id = _run(_insert_note(ws_env.user_id, aspect_map=json.dumps(_FOCUS_MAP)))
    old_id = _run(_insert_feedback(note_id, ws_env.user_id, "古い改善", _FOCUS_ITEMS))
    latest_id = _run(_insert_feedback(note_id, ws_env.user_id, "新しい改善", _FOCUS_ITEMS))
    _run(_insert_memo_from_feedback(ws_env.user_id, note_id, latest_id if memo_on_latest else old_id, "a2"))
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_review", "note_id": str(note_id)})
        assert ws.receive_json()["type"] == "session_started"
        ws.receive_json()
        ws.receive_json()
    state: dict[str, Any] = ws_env.graph.stream_inputs[0]
    return state


def test_start_review_puts_memo_aspects_first(ws_env: SimpleNamespace) -> None:
    initial = _start_review_with_memo(ws_env, memo_on_latest=True)

    assert initial["review_priority_aspects"] == ["前提条件"]


def test_start_review_ignores_memos_of_older_feedbacks(ws_env: SimpleNamespace) -> None:
    initial = _start_review_with_memo(ws_env, memo_on_latest=False)

    assert "review_priority_aspects" not in initial


def test_review_session_never_carries_learning_progress(ws_env: SimpleNamespace) -> None:
    note_id = _run(_insert_note(ws_env.user_id))
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 3,
        "covered_aspects": [{"aspect": "計算量", "reached_depth": "exemplified"}],
    }

    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_review", "note_id": str(note_id)})
        assert ws.receive_json()["type"] == "session_started"
        assert ws.receive_json()["type"] == "assistant_message_chunk"
        assert ws.receive_json() == {
            "type": "assistant_message_end",
            "progress": None,
            "topic": None,
            "end_confirmation": None,
            "note_peek_available": False,
        }

        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "復習の回答です"})
        assert ws.receive_json()["type"] == "assistant_message_chunk"
        assert ws.receive_json() == {
            "type": "assistant_message_end",
            "progress": None,
            "topic": None,
            "end_confirmation": None,
            "note_peek_available": False,
        }


def test_duplicate_client_message_id_is_ignored(ws_env: SimpleNamespace) -> None:
    """同一 client_message_id の再送は、既存の応答をそのままにグラフを再実行しない。"""
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = UUID(_start_learning(ws))

        call_count = 0
        original_astream = ws_env.graph.astream

        async def counting_astream(
            graph_input: Any, config: Any, stream_mode: str = "messages"
        ) -> AsyncIterator[tuple[AIMessageChunk, dict[str, Any]]]:
            nonlocal call_count
            call_count += 1
            async for item in original_astream(graph_input, config, stream_mode):
                yield item

        ws_env.graph.astream = counting_astream

        client_message_id = str(uuid4())
        ws.send_json(
            {"type": "user_message", "client_message_id": client_message_id, "content": "二分探索は半分に絞る手法です"}
        )
        _drain_assistant_turn(ws)

        ws.send_json(
            {"type": "user_message", "client_message_id": client_message_id, "content": "二分探索は半分に絞る手法です"}
        )

        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "別の発言です"})
        _drain_assistant_turn(ws)
        _wait_until_handled(ws)

    assert call_count == 2
    rows = _run(_fetch_messages(session_id))
    assert [(r["role"], r["message_order"]) for r in rows] == [
        ("user", 1),
        ("assistant", 2),
        ("user", 3),
        ("assistant", 4),
        ("user", 5),
        ("assistant", 6),
    ]
    assert [r["content"] for r in rows if r["role"] == "user"] == [
        "二分探索",
        "二分探索は半分に絞る手法です",
        "別の発言です",
    ]


def test_voice_message_is_stored_with_its_raw_transcript_but_not_sent_to_the_graph(
    ws_env: SimpleNamespace,
) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = UUID(_start_learning(ws))

        ws.send_json(
            {
                "type": "user_message",
                "client_message_id": str(uuid4()),
                "content": "二分探索は半分に絞る手法です",
                "raw_transcript": "二分探索は半分にしぼる手法です",
            }
        )
        _drain_assistant_turn(ws)

    rows = _run(_fetch_user_input_modes(session_id))
    assert [(r["content"], r["input_mode"], r["raw_transcript"]) for r in rows] == [
        ("二分探索", "text", None),
        ("二分探索は半分に絞る手法です", "voice", "二分探索は半分にしぼる手法です"),
    ]
    human_messages = [
        message
        for values, _ in ws_env.graph.update_calls
        for message in values.get("messages", [])
        if message.content == "二分探索は半分に絞る手法です"
    ]
    assert len(human_messages) == 1
    assert "raw_transcript" not in human_messages[0].additional_kwargs


def test_viewed_note_is_stored_on_the_human_message(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        for content, viewed in (("ノートを見た説明", True), ("見ていない説明", False)):
            ws.send_json(
                {
                    "type": "user_message",
                    "client_message_id": str(uuid4()),
                    "content": content,
                    "viewed_note": viewed,
                }
            )
            _drain_assistant_turn(ws)

    sent = {
        message.content: message
        for values, _ in ws_env.graph.update_calls
        for message in values.get("messages", [])
        if isinstance(message, HumanMessage)
    }
    assert sent["ノートを見た説明"].additional_kwargs["viewed_note"] is True
    assert "viewed_note" not in sent["見ていない説明"].additional_kwargs


def test_user_message_over_the_length_limit_is_rejected_without_saving(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = UUID(_start_learning(ws))
        updates_before = len(ws_env.graph.update_calls)

        ws.send_json(
            {
                "type": "user_message",
                "client_message_id": str(uuid4()),
                "content": "あ" * (MAX_MESSAGE_CONTENT_LENGTH + 1),
            }
        )

        err = ws.receive_json()
        assert err["type"] == "error"
        assert f"{MAX_MESSAGE_CONTENT_LENGTH:,}字" in err["detail"]

    rows = _run(_fetch_messages(session_id))
    assert [r["content"] for r in rows if r["role"] == "user"] == ["二分探索"]
    assert len(ws_env.graph.update_calls) == updates_before


def test_user_message_llm_failure_rolls_back_without_failing_session(ws_env: SimpleNamespace) -> None:
    """ターン応答生成中の例外は、セッションを failed にせず未応答のユーザー発話だけを巻き戻す。"""
    pending = HumanMessage(content="二分探索は半分に絞る手法です")
    pending.id = "pending-turn"

    async def failing_astream(
        graph_input: Any, config: Any, stream_mode: str = "messages"
    ) -> AsyncIterator[tuple[AIMessageChunk, dict[str, Any]]]:
        for _ in ():
            yield _  # pragma: no cover
        raise RuntimeError("LLM boom")

    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = UUID(_start_learning(ws))

        ws_env.graph.state_values = {
            "should_generate_note": False,
            "turn_count": 1,
            "messages": [pending],
        }
        ws_env.graph.astream = failing_astream

        ws.send_json(
            {"type": "user_message", "client_message_id": str(uuid4()), "content": "二分探索は半分に絞る手法です"}
        )

        err = ws.receive_json()
        assert err["type"] == "error"

        rolled_back = ws.receive_json()
        assert rolled_back == {"type": "pending_message_rolled_back", "content": "二分探索は半分に絞る手法です"}

        assert [r["role"] for r in _run(_fetch_messages(session_id))] == ["user", "assistant"]
        removals = [
            values for values, _ in ws_env.graph.update_calls if isinstance(values["messages"][0], RemoveMessage)
        ]
        assert removals and removals[-1]["messages"][0].id == "pending-turn"

        session = _run(_fetch_session(session_id))
        assert session is not None
        assert session["status"] == "in_progress"


def test_cancel_last_message_success(ws_env: SimpleNamespace) -> None:
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 2,
        "messages": [
            HumanMessage(content="私の回答", id="h1"),
            AIMessage(content="AI の応答", id="a1"),
        ],
    }

    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)

        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "私の回答"})
        _drain_assistant_turn(ws)

        ws.send_json({"type": "cancel_last_message"})
        res = ws.receive_json()
        assert res["type"] == "cancel_last_message_success"
        assert res["cancelled_content"] == "私の回答"


def test_cancel_without_session_returns_error(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "cancel_last_message"})

        res = ws.receive_json()
        assert res["type"] == "cancel_last_message_error"
        assert "セッションが開始されていません。ページを再読み込みしてください" in res["detail"]


def test_cancel_before_first_turn_returns_error(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)

        ws.send_json({"type": "cancel_last_message"})
        res = ws.receive_json()
        assert res["type"] == "cancel_last_message_error"
        assert "取り消せる発言がありません" in res["detail"]


def test_end_session_returns_session_ended(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        ws_env.graph.state_values = _MAP_WITH_CONTENT

        ws.send_json({"type": "end_session"})
        assert ws.receive_json()["type"] == "session_ended"


def test_resuming_in_another_connection_takes_the_session_over(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as old:
        _authenticate(old)
        session_id = _start_learning(old)

        with client.websocket_connect("/ws/chat") as new:
            _authenticate(new)
            new.send_json({"type": "resume_session", "session_id": session_id})
            assert new.receive_json()["type"] == "session_resumed"

            _send(old, "古い画面からの発言")
            taken_over = old.receive_json()
            assert taken_over["type"] == "session_taken_over"
            with pytest.raises(WebSocketDisconnect):
                old.receive_json()

            _send(new, "新しい画面からの発言")
            _drain_assistant_turn(new)
            _wait_until_handled(new)

            rows = _run(_fetch_messages(UUID(session_id)))
            assert [(r["message_order"], r["content"]) for r in rows if r["role"] == "user"] == [
                (1, "二分探索"),
                (3, "新しい画面からの発言"),
            ]
            assert _run(_session_status(UUID(session_id))) == "in_progress"


@pytest.mark.parametrize("request_type", ["cancel_last_message", "end_session"])
def test_a_taken_over_connection_cannot_cancel_or_end_the_session(ws_env: SimpleNamespace, request_type: str) -> None:
    ws_env.graph.state_values = _MAP_WITH_CONTENT
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as old:
        _authenticate(old)
        session_id = _start_learning(old)

        with client.websocket_connect("/ws/chat") as new:
            _authenticate(new)
            new.send_json({"type": "resume_session", "session_id": session_id})
            assert new.receive_json()["type"] == "session_resumed"

            old.send_json({"type": request_type})
            assert old.receive_json()["type"] == "session_taken_over"

            assert _run(_session_status(UUID(session_id))) == "in_progress"
            assert ws_env.graph.update_calls == []


class StatefulGraph(FakeGraph):
    """aupdate_state を state に反映し、返したチェックポイントの時点の state を aget_state で読める。"""

    def __init__(self) -> None:
        super().__init__()
        self.checkpoints: list[dict[str, Any]] = []

    async def aget_state(self, config: Any) -> SimpleNamespace:
        checkpoint_id = (config.get("configurable") or {}).get("checkpoint_id")
        return SimpleNamespace(values=self.state_values if checkpoint_id is None else self.checkpoints[checkpoint_id])

    async def aupdate_state(  # type: ignore[override]
        self, config: Any, values: dict[str, Any], as_node: str | None = None
    ) -> dict[str, Any]:
        await super().aupdate_state(config, values, as_node)
        messages = list(self.state_values.get("messages") or [])
        for message in values.get("messages", []):
            if isinstance(message, RemoveMessage):
                messages = [m for m in messages if m.id != message.id]
            else:
                messages.append(message)
        self.state_values = {**self.state_values, **values, "messages": messages}
        self.checkpoints.append(self.state_values)
        return {"configurable": {**config.get("configurable", {}), "checkpoint_id": len(self.checkpoints) - 1}}


def _block_turn_stream(graph: FakeGraph, on_release: Any = None) -> SimpleNamespace:
    """ターンの応答の生成を release まで止める。開始の応答はそのまま流す。"""
    flags = SimpleNamespace(started=threading.Event(), release=threading.Event(), cancelled=False)
    original = graph.astream

    async def astream(
        graph_input: Any, config: Any, stream_mode: str = "messages"
    ) -> AsyncIterator[tuple[AIMessageChunk, dict[str, Any]]]:
        if graph_input is not None:
            async for item in original(graph_input, config, stream_mode):
                yield item
            return
        flags.started.set()
        try:
            while not flags.release.is_set():
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            flags.cancelled = True
            raise
        if on_release is not None:
            on_release()
        yield AIMessageChunk(content="遅れた応答"), {"langgraph_node": "learning_dialogue"}

    graph.astream = astream  # type: ignore[method-assign]
    return flags


async def _turn_started_at(session_id: UUID) -> Any:
    session = await _fetch_session(session_id)
    assert session is not None
    return session["turn_started_at"]


async def _connection_id(session_id: UUID) -> Any:
    session = await _fetch_session(session_id)
    assert session is not None
    return session["connection_id"]


def _receive_until(ws: Any, message_type: str) -> dict[str, Any]:
    while True:
        message = ws.receive_json()
        if message["type"] == message_type:
            return cast(dict[str, Any], message)


def test_a_turn_in_flight_is_abandoned_when_another_connection_takes_over(
    ws_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(chat, "TURN_OWNERSHIP_POLL_SECONDS", 0.05)
    monkeypatch.setattr(chat, "TURN_SETTLE_POLL_SECONDS", 0.02)
    flags = _block_turn_stream(ws_env.graph)
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as old:
        _authenticate(old)
        session_id = UUID(_start_learning(old))
        ws_env.graph.state_values = {
            "should_generate_note": False,
            "turn_count": 1,
            "messages": [
                HumanMessage(content="二分探索"),
                AIMessage(content="こんにちは"),
                HumanMessage(content="途中の発言", id="in-flight"),
            ],
        }
        _send(old, "途中の発言")
        assert flags.started.wait(5)

        with client.websocket_connect("/ws/chat") as new:
            _authenticate(new)
            new.send_json({"type": "resume_session", "session_id": str(session_id)})
            assert new.receive_json()["type"] == "session_resumed"
            assert new.receive_json() == {"type": "pending_message_rolled_back", "content": "途中の発言"}
            assert old.receive_json()["type"] == "session_taken_over"

    assert flags.cancelled
    assert [(r["role"], r["message_order"]) for r in _run(_fetch_messages(session_id))] == [
        ("user", 1),
        ("assistant", 2),
    ]
    assert _run(_turn_started_at(session_id)) is None


def test_a_turn_finished_after_a_takeover_is_undone_instead_of_saved(
    ws_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(chat, "TURN_OWNERSHIP_POLL_SECONDS", 30.0)
    monkeypatch.setattr(chat, "TURN_SETTLE_POLL_SECONDS", 0.02)
    graph = StatefulGraph()
    ws_env.app.state.graph = graph

    def finish_the_node() -> None:
        graph.state_values = {
            **graph.state_values,
            "turn_count": 2,
            "end_confirmation": "offered",
            "messages": [*graph.state_values["messages"], AIMessage(content="遅れた応答", id="late")],
        }

    flags = _block_turn_stream(graph, on_release=finish_the_node)
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as old:
        _authenticate(old)
        session_id = UUID(_start_learning(old))
        old_connection = _run(_connection_id(session_id))
        graph.state_values = {
            "should_generate_note": False,
            "turn_count": 1,
            "end_confirmation": None,
            "messages": [HumanMessage(content="二分探索", id="h1"), AIMessage(content="こんにちは", id="a1")],
        }
        _send(old, "途中の発言")
        assert flags.started.wait(5)

        with client.websocket_connect("/ws/chat") as new:
            _authenticate(new)
            new.send_json({"type": "resume_session", "session_id": str(session_id)})
            for _ in range(500):
                if _run(_connection_id(session_id)) != old_connection:
                    break
            flags.release.set()

            assert new.receive_json()["type"] == "session_resumed"
            assert new.receive_json() == {"type": "pending_message_rolled_back", "content": "途中の発言"}
            _receive_until(old, "session_taken_over")

    assert [m.id for m in graph.state_values["messages"]] == ["h1", "a1"]
    assert graph.state_values["turn_count"] == 1
    assert graph.state_values["end_confirmation"] is None
    assert [(r["role"], r["message_order"]) for r in _run(_fetch_messages(session_id))] == [
        ("user", 1),
        ("assistant", 2),
    ]
    assert _run(_turn_started_at(session_id)) is None


def test_resume_stops_waiting_for_a_turn_nobody_finishes(
    ws_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(chat, "TURN_SETTLE_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(chat, "TURN_SETTLE_POLL_SECONDS", 0.02)
    session_id = uuid4()
    _run(_insert_session(session_id, ws_env.user_id, graph_version=GRAPH_VERSION))
    _run(_insert_messages(session_id, [("user", "プロセス"), ("assistant", "話してみて")]))

    async def mark_turn_started() -> None:
        conn = await asyncpg.connect(TEST_DATABASE_URL)
        try:
            await conn.execute("UPDATE dialogue_sessions SET turn_started_at = NOW() WHERE id = $1", str(session_id))
        finally:
            await conn.close()

    _run(mark_turn_started())

    received = _resume_and_collect(ws_env, session_id)

    assert received[0]["type"] == "session_resumed"
    assert _run(_turn_started_at(session_id)) is None


def _receive_cancel_reply(ws: Any) -> dict[str, Any]:
    while True:
        message = ws.receive_json()
        if message["type"] in ("cancel_last_message_success", "cancel_last_message_error"):
            return cast(dict[str, Any], message)


def _release_later(flags: SimpleNamespace, seconds: float = 10.0) -> None:
    timer = threading.Timer(seconds, flags.release.set)
    timer.daemon = True
    timer.start()


def _hold_turn_saving(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """返答を流し終えた後、保存（finish_turn）の手前で go まで止める。"""
    gate = SimpleNamespace(saving=threading.Event(), go=threading.Event())
    original = dialogue_session_repository.finish_turn

    async def finish_turn(conn: Any, session_id: UUID, connection_id: UUID) -> bool:
        gate.saving.set()
        for _ in range(500):
            if gate.go.is_set():
                break
            await asyncio.sleep(0.01)
        return await original(conn, session_id, connection_id)

    monkeypatch.setattr(dialogue_session_repository, "finish_turn", finish_turn)
    return gate


def _start_with_stateful_graph(ws_env: SimpleNamespace) -> StatefulGraph:
    graph = StatefulGraph()
    ws_env.app.state.graph = graph
    return graph


_BEFORE_STOP = {
    "should_generate_note": False,
    "turn_count": 1,
    "messages": [HumanMessage(content="二分探索", id="h1"), AIMessage(content="こんにちは", id="a1")],
}


def test_stop_during_a_turn_cancels_the_generation_and_returns_the_message(ws_env: SimpleNamespace) -> None:
    graph = _start_with_stateful_graph(ws_env)
    flags = _block_turn_stream(graph)
    _release_later(flags)
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = UUID(_start_learning(ws))
        graph.state_values = dict(_BEFORE_STOP)
        _send(ws, "途中の発言")
        assert flags.started.wait(5)

        ws.send_json({"type": "cancel_last_message"})
        res = _receive_cancel_reply(ws)

        assert (res["type"], res.get("cancelled_content")) == ("cancel_last_message_success", "途中の発言")
        assert flags.cancelled is True
        assert [m.id for m in graph.state_values["messages"]] == ["h1", "a1"]
        assert [(r["role"], r["message_order"]) for r in _run(_fetch_messages(session_id))] == [
            ("user", 1),
            ("assistant", 2),
        ]
        assert _run(_turn_started_at(session_id)) is None

        flags.release.set()
        _send(ws, "送り直し")
        _drain_assistant_turn(ws)
        _wait_until_handled(ws)

    assert [(r["role"], r["message_order"], r["content"]) for r in _run(_fetch_messages(session_id))] == [
        ("user", 1, "二分探索"),
        ("assistant", 2, "こんにちは"),
        ("user", 3, "送り直し"),
        ("assistant", 4, "遅れた応答"),
    ]


def test_stop_rewinds_the_turn_to_before_the_message(ws_env: SimpleNamespace) -> None:
    graph = _start_with_stateful_graph(ws_env)
    flags = _block_turn_stream(graph)
    _release_later(flags)
    review_points = [{"id": "p1", "status": "pending"}]
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        graph.state_values = {
            **_BEFORE_STOP,
            "turn_count": 3,
            "map_covered": [],
            "review_points": review_points,
            "end_confirmation": None,
            "pending_topic_correction": None,
        }
        _send(ws, "途中の発言")
        assert flags.started.wait(5)
        graph.state_values = {
            **graph.state_values,
            "turn_count": 4,
            "map_covered": [{"aspect_id": "a1", "reached_stage": "defined"}],
            "review_points": [{"id": "p1", "status": "answered"}],
            "end_confirmation": "offered",
            "pending_topic_correction": {"new_topic": "別のトピック"},
            "review_answered": True,
            "messages": [*graph.state_values["messages"], AIMessage(content="途中まで", id="partial")],
        }

        ws.send_json({"type": "cancel_last_message"})
        assert _receive_cancel_reply(ws)["type"] == "cancel_last_message_success"

    values = graph.state_values
    assert values["turn_count"] == 3
    assert values["map_covered"] == []
    assert values["review_points"] == review_points
    assert values["end_confirmation"] is None
    assert values["pending_topic_correction"] is None
    assert values["review_answered"] is None
    assert [m.id for m in values["messages"]] == ["h1", "a1"]


def test_stop_of_an_intake_answer_is_refused_and_the_turn_finishes(ws_env: SimpleNamespace) -> None:
    graph = _start_with_stateful_graph(ws_env)
    flags = _block_turn_stream(graph)
    _release_later(flags)
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = UUID(_start_learning(ws))
        graph.state_values = {
            **_BEFORE_STOP,
            "messages": [
                HumanMessage(content="二分探索", id="h1"),
                AIMessage(content="教えてください", id="a1", additional_kwargs={"intake_card": _CARD}),
            ],
        }
        ws.send_json(
            {
                "type": "user_message",
                "client_message_id": str(uuid4()),
                "content": "教材: 書籍",
                "intake_answers": {"source": ["書籍"]},
            }
        )
        assert flags.started.wait(5)

        ws.send_json({"type": "cancel_last_message"})
        refused = _receive_cancel_reply(ws)
        assert refused == {"type": "cancel_last_message_error", "detail": "聞き取りへの回答は取り消せません"}
        assert flags.cancelled is False

        flags.release.set()
        _receive_until(ws, "assistant_message_end")
        _wait_until_handled(ws)

    assert [(r["role"], r["message_order"]) for r in _run(_fetch_messages(session_id))] == [
        ("user", 1),
        ("assistant", 2),
        ("user", 3),
        ("assistant", 4),
    ]


def test_stop_after_the_reply_is_saved_cancels_both_rows(
    ws_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph = _start_with_stateful_graph(ws_env)

    def finish_the_node() -> None:
        graph.state_values = {
            **graph.state_values,
            "turn_count": 2,
            "messages": [*graph.state_values["messages"], AIMessage(content="遅れた応答", id="reply")],
        }

    flags = _block_turn_stream(graph, on_release=finish_the_node)
    flags.release.set()
    gate = _hold_turn_saving(monkeypatch)
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = UUID(_start_learning(ws))
        graph.state_values = dict(_BEFORE_STOP)
        _send(ws, "途中の発言")
        assert gate.saving.wait(5)

        ws.send_json({"type": "cancel_last_message"})
        gate.go.set()
        res = _receive_cancel_reply(ws)

    assert res["type"] == "cancel_last_message_success"
    assert res["cancelled_content"] == "途中の発言"
    assert [m.id for m in graph.state_values["messages"]] == ["h1", "a1"]
    assert [(r["role"], r["message_order"]) for r in _run(_fetch_messages(session_id))] == [
        ("user", 1),
        ("assistant", 2),
    ]


def test_a_message_other_than_cancel_during_a_turn_is_handled_after_the_reply(ws_env: SimpleNamespace) -> None:
    flags = _block_turn_stream(ws_env.graph)
    _release_later(flags)
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        _send(ws, "途中の発言")
        assert flags.started.wait(5)

        ws.send_json({"type": "unknown"})
        flags.release.set()

        received = [ws.receive_json() for _ in range(3)]

    assert [m["type"] for m in received] == ["assistant_message_chunk", "assistant_message_end", "error"]
    assert received[-1]["code"] == "invalid_message"
    assert flags.cancelled is False


def _fail_turn_after_the_next_message_arrives(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(human: Any, human_config: Any, ctx: Any, deps: Any) -> Any:
        await asyncio.wait({deps.inbox.receiving()})
        raise RuntimeError("generation failed")

    monkeypatch.setattr(chat, "_stream_turn_while_held", fail)


def test_a_stop_queued_when_the_turn_fails_does_not_cancel_the_previous_turn(
    ws_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _start_with_stateful_graph(ws_env)
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = UUID(_start_learning(ws))
        for content in ("1つ目の発言", "2つ目の発言"):
            _send(ws, content)
            _drain_assistant_turn(ws)
        _wait_until_handled(ws)
        _fail_turn_after_the_next_message_arrives(monkeypatch)

        _send(ws, "失敗する発言")
        ws.send_json({"type": "cancel_last_message"})

        assert ws.receive_json()["code"] == "turn_failed"
        assert ws.receive_json() == {"type": "pending_message_rolled_back", "content": "失敗する発言"}
        assert ws.receive_json() == {"type": "cancel_last_message_error", "detail": "取り消せる発言がありません"}
        _wait_until_handled(ws)

    assert [(r["role"], r["content"]) for r in _run(_fetch_messages(session_id))][2:] == [
        ("user", "1つ目の発言"),
        ("assistant", "こんにちは"),
        ("user", "2つ目の発言"),
        ("assistant", "こんにちは"),
    ]


def test_a_message_other_than_stop_queued_when_the_turn_fails_is_handled_next(
    ws_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _start_with_stateful_graph(ws_env)
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        _fail_turn_after_the_next_message_arrives(monkeypatch)

        _send(ws, "失敗する発言")
        ws.send_json({"type": "unknown"})

        assert ws.receive_json()["code"] == "turn_failed"
        assert ws.receive_json()["type"] == "pending_message_rolled_back"
        assert ws.receive_json()["code"] == "invalid_message"


async def test_a_receive_that_raised_stays_for_the_next_read() -> None:
    class Disconnected:
        async def receive_text(self) -> str:
            raise WebSocketDisconnect()

    inbox = chat.Inbox(cast(Any, Disconnected()))
    await asyncio.wait({inbox.receiving()})

    assert inbox.take_ready_if(chat._is_cancel_request) is None
    with pytest.raises(WebSocketDisconnect):
        await inbox.next()


def test_a_stop_after_the_end_is_confirmed_is_ignored(
    ws_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = _hold_turn_saving(monkeypatch)
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = _start_learning(ws)
        ws_env.graph.stream_chunks = []
        ws_env.graph.state_values = {**_MAP_WITH_CONTENT, "end_confirmation": "confirmed"}
        _send(ws, "はい、終わります")
        assert gate.saving.wait(5)

        ws.send_json({"type": "cancel_last_message"})
        gate.go.set()
        assert ws.receive_json()["type"] == "assistant_message_end"
        assert ws.receive_json()["type"] == "session_ended"

    assert [r["role"] for r in _run(_fetch_messages(UUID(session_id)))] == ["user", "assistant", "user"]
    assert not any("end_confirmation" in values for values, _ in ws_env.graph.update_calls)


@pytest.mark.asyncio(loop_scope="session")
async def test_a_disconnect_during_a_turn_still_saves_the_reply(
    test_pool: asyncpg.Pool, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = test_user["id"]
    async with test_pool.acquire() as conn:
        await user_consent_repository.record(conn, user_id, TERMS_VERSION)

    async def fake_get_pool() -> asyncpg.Pool:
        return test_pool

    monkeypatch.setattr(chat, "get_pool", fake_get_pool)
    monkeypatch.setattr(ws_auth, "verify_jwt", lambda token: {"sub": user_id})

    disconnected = asyncio.Event()

    class DisconnectingWebSocket(FakeWebSocket):
        async def receive_text(self) -> str:
            if not self._inbound:
                disconnected.set()
            return await super().receive_text()

    graph = FakeGraph()
    start_stream = graph.astream

    async def astream_after_disconnect(
        graph_input: Any, config: Any, stream_mode: str = "messages"
    ) -> AsyncIterator[tuple[AIMessageChunk, dict[str, Any]]]:
        if graph_input is None:
            await asyncio.wait_for(disconnected.wait(), 5)
            yield AIMessageChunk(content="切断の後の応答"), {"langgraph_node": "learning_dialogue"}
            return
        async for item in start_stream(graph_input, config, stream_mode):
            yield item

    graph.astream = astream_after_disconnect  # type: ignore[method-assign]
    inbound = [
        json.dumps({"type": "authenticate", "token": "x", "protocol_version": PROTOCOL_VERSION}),
        json.dumps({"type": "start_learning", "topic": "二分探索"}),
        json.dumps({"type": "user_message", "client_message_id": str(uuid4()), "content": "途中の発言"}),
    ]
    ws = DisconnectingWebSocket(graph, inbound)

    await chat.websocket_chat(cast(Any, ws))

    session_id = next(json.loads(raw)["session_id"] for raw in ws.sent if json.loads(raw)["type"] == "session_started")
    async with test_pool.acquire() as conn:
        status = await conn.fetchval("SELECT status FROM dialogue_sessions WHERE id = $1", session_id)
        rows = await conn.fetch(
            "SELECT role, content FROM dialogue_messages WHERE dialogue_session_id = $1 ORDER BY message_order",
            session_id,
        )
    assert status == "disconnect"
    assert [(r["role"], r["content"]) for r in rows][-2:] == [("user", "途中の発言"), ("assistant", "切断の後の応答")]


def test_resume_with_stale_graph_version_is_rejected(ws_env: SimpleNamespace) -> None:
    session_id = uuid4()
    _run(_insert_session(session_id, ws_env.user_id, graph_version=1))

    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "resume_session", "session_id": str(session_id)})

        err = ws.receive_json()
        assert err["type"] == "error"
        assert "再開できません" in err["detail"]

    row = _run(_fetch_session(session_id))
    assert row is not None
    assert row["status"] == "abandoned"


def test_resume_rolls_back_a_user_message_left_without_a_response(ws_env: SimpleNamespace) -> None:
    """応答生成中に切断されたターンは、再開時に state と DB から取り消される。

    残したままだとユーザーは同じ内容を再送するしかなく、履歴に同一発言が二重に残る。
    """
    session_id = uuid4()
    _run(_insert_session(session_id, ws_env.user_id, graph_version=GRAPH_VERSION))
    _run(_insert_messages(session_id, [("user", "プロセス"), ("assistant", "話してみて"), ("user", "実行単位です")]))
    pending = HumanMessage(content="実行単位です")
    pending.id = "pending-1"
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 1,
        "messages": [HumanMessage(content="プロセス"), AIMessage(content="話してみて"), pending],
    }

    received = _resume_and_collect(ws_env, session_id)

    rolled_back = [m for m in received if m["type"] == "pending_message_rolled_back"]
    assert rolled_back == [{"type": "pending_message_rolled_back", "content": "実行単位です"}]
    assert [(r["role"], r["message_order"]) for r in _run(_fetch_messages(session_id))] == [
        ("user", 1),
        ("assistant", 2),
    ]
    removals = [values for values, _ in ws_env.graph.update_calls if "messages" in values]
    assert removals and removals[0]["messages"][0].id == "pending-1"
    assert all("turn_count" not in values for values, _ in ws_env.graph.update_calls)


def test_resume_rolls_back_a_row_missing_from_state(ws_env: SimpleNamespace) -> None:
    """state への反映前に落ちた場合は DB 側にだけ残るので、そこも取り消す。"""
    session_id = uuid4()
    _run(_insert_session(session_id, ws_env.user_id, graph_version=GRAPH_VERSION))
    _run(_insert_messages(session_id, [("user", "プロセス"), ("assistant", "話してみて"), ("user", "実行単位です")]))
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 1,
        "messages": [HumanMessage(content="プロセス"), AIMessage(content="話してみて")],
    }

    received = _resume_and_collect(ws_env, session_id)

    assert [m["type"] for m in received if m["type"] == "pending_message_rolled_back"] == [
        "pending_message_rolled_back"
    ]
    assert [r["message_order"] for r in _run(_fetch_messages(session_id))] == [1, 2]
    assert all("messages" not in values for values, _ in ws_env.graph.update_calls)


def test_resume_keeps_a_completed_turn_untouched(ws_env: SimpleNamespace) -> None:
    session_id = uuid4()
    _run(_insert_session(session_id, ws_env.user_id, graph_version=GRAPH_VERSION))
    _run(_insert_messages(session_id, [("user", "プロセス"), ("assistant", "話してみて")]))
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 1,
        "messages": [HumanMessage(content="プロセス"), AIMessage(content="話してみて")],
    }

    received = _resume_and_collect(ws_env, session_id)

    assert [m["type"] for m in received] == ["session_resumed", "session_ended"]
    assert [r["message_order"] for r in _run(_fetch_messages(session_id))] == [1, 2]


def test_resume_restores_learning_progress(ws_env: SimpleNamespace) -> None:
    session_id = uuid4()
    _run(_insert_session(session_id, ws_env.user_id, graph_version=GRAPH_VERSION))
    _run(_insert_messages(session_id, [("user", "プロセス"), ("assistant", "話してみて")]))
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 1,
        "messages": [HumanMessage(content="プロセス"), AIMessage(content="話してみて")],
        "covered_aspects": [{"aspect": "実行単位", "reached_depth": "applied"}],
    }

    received = _resume_and_collect(ws_env, session_id)

    assert received[0]["type"] == "session_resumed"
    assert received[0]["progress"] == {
        "reached_aspects": ["実行単位"],
        "target_count": 3,
        "is_complete": False,
        "aspects": [],
        "intake": None,
    }


def test_resume_during_intake_carries_no_progress(ws_env: SimpleNamespace) -> None:
    session_id = uuid4()
    _run(_insert_session(session_id, ws_env.user_id, graph_version=GRAPH_VERSION))
    _run(_insert_messages(session_id, [("user", "f文字列"), ("assistant", "いくつか教えてください")]))
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 0,
        "messages": [HumanMessage(content="f文字列"), AIMessage(content="いくつか教えてください")],
        "intake_complete": False,
    }

    received = _resume_and_collect(ws_env, session_id)

    assert received[0]["type"] == "session_resumed"
    assert received[0]["progress"] is None


def test_resume_progress_lists_map_aspects_without_core_questions(ws_env: SimpleNamespace) -> None:
    session_id = uuid4()
    _run(_insert_session(session_id, ws_env.user_id, graph_version=GRAPH_VERSION))
    _run(_insert_messages(session_id, [("user", "f文字列"), ("assistant", "話してみて")]))
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 1,
        "messages": [HumanMessage(content="f文字列"), AIMessage(content="話してみて")],
        "intake_complete": True,
        "depth_map": {
            "topic": "f文字列",
            "aspects": [
                {
                    "id": "embed",
                    "name": "値の埋め込み方",
                    "is_core": True,
                    "defined_question": "埋め込みの定義を問う核心",
                    "reasoned_question": "埋め込みの理由を問う核心",
                    "applied_question": "埋め込みの応用を問う核心",
                }
            ],
        },
        "map_covered": [{"aspect_id": "embed", "reached_stage": "defined"}],
    }

    received = _resume_and_collect(ws_env, session_id)

    progress = received[0]["progress"]
    assert progress["aspects"] == [{"name": "値の埋め込み方", "is_core": True, "reached_stage": "defined"}]
    assert "核心" not in json.dumps(progress, ensure_ascii=False)
    assert "embed" not in json.dumps(progress, ensure_ascii=False)


def _keyword_state(session_id: str, user_id: str) -> dict[str, Any]:
    return {
        "should_generate_note": False,
        "turn_count": 2,
        "session_type": "learning",
        "dialogue_session_id": session_id,
        "user_id": user_id,
        "topic": "TCP/IPの仕組み",
        "learning_goal": "障害を調べたい",
        "intake_complete": True,
        "depth_map": {"topic": "TCP/IPの仕組み", "aspects": [{"id": "a1", "name": "再送制御", "is_core": True}]},
    }


def test_turn_schedules_transcription_keywords_from_the_state(
    ws_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    scheduled: list[tuple[UUID, str, KeywordSource]] = []
    monkeypatch.setattr(chat, "schedule_transcription_keywords", lambda *args: scheduled.append(args))
    session_id = uuid4()
    ws_env.graph.state_values = _keyword_state(str(session_id), ws_env.user_id)

    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)

    assert scheduled == [
        (session_id, ws_env.user_id, KeywordSource("TCP/IPの仕組み", ("再送制御",), "障害を調べたい"))
    ]


def test_resume_schedules_transcription_keywords(ws_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    scheduled: list[tuple[UUID, str, KeywordSource]] = []
    monkeypatch.setattr(chat, "schedule_transcription_keywords", lambda *args: scheduled.append(args))
    session_id = uuid4()
    _run(_insert_session(session_id, ws_env.user_id, graph_version=GRAPH_VERSION))
    _run(_insert_messages(session_id, [("user", "TCP"), ("assistant", "話してみて")]))
    ws_env.graph.state_values = {
        **_keyword_state(str(session_id), ws_env.user_id),
        "messages": [HumanMessage(content="TCP"), AIMessage(content="話してみて")],
    }

    _resume_and_collect(ws_env, session_id)

    assert [(sid, uid) for sid, uid, _ in scheduled][:1] == [(session_id, ws_env.user_id)]


def test_intake_turn_schedules_no_transcription_keywords(
    ws_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    scheduled: list[Any] = []
    monkeypatch.setattr(chat, "schedule_transcription_keywords", lambda *args: scheduled.append(args))
    ws_env.graph.state_values = {
        **_keyword_state(str(uuid4()), ws_env.user_id),
        "intake_complete": False,
        "depth_map": None,
    }

    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)

    assert scheduled == []


def test_resume_review_session_never_carries_learning_progress(ws_env: SimpleNamespace) -> None:
    note_id = _run(_insert_note(ws_env.user_id))
    session_id = uuid4()
    _run(_insert_review_session(session_id, ws_env.user_id, note_id, graph_version=GRAPH_VERSION))
    _run(_insert_messages(session_id, [("user", "プロセス"), ("assistant", "話してみて")]))
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 1,
        "messages": [HumanMessage(content="プロセス"), AIMessage(content="話してみて")],
        "covered_aspects": [{"aspect": "実行単位", "reached_depth": "applied"}],
    }

    received = _resume_and_collect(ws_env, session_id)

    assert received[0]["type"] == "session_resumed"
    assert received[0]["progress"] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_disconnect_marks_session_as_disconnect(
    test_pool: asyncpg.Pool, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = test_user["id"]
    async with test_pool.acquire() as conn:
        await user_consent_repository.record(conn, user_id, TERMS_VERSION)

    async def fake_get_pool() -> asyncpg.Pool:
        return test_pool

    monkeypatch.setattr(chat, "get_pool", fake_get_pool)
    monkeypatch.setattr(ws_auth, "verify_jwt", lambda token: {"sub": user_id})

    graph = FakeGraph()
    inbound = [
        json.dumps({"type": "authenticate", "token": "x", "protocol_version": PROTOCOL_VERSION}),
        json.dumps({"type": "start_learning", "topic": "二分探索"}),
    ]
    ws = FakeWebSocket(graph, inbound)

    await chat.websocket_chat(cast(Any, ws))

    session_id: str | None = None
    for raw in ws.sent:
        msg = json.loads(raw)
        if msg["type"] == "session_started":
            session_id = msg["session_id"]
    assert session_id is not None

    async with test_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT status FROM dialogue_sessions WHERE id = $1", session_id)
    assert row is not None
    assert row["status"] == "disconnect"


@pytest.mark.asyncio(loop_scope="session")
async def test_disconnecting_after_a_takeover_leaves_the_session_to_the_new_connection(
    test_pool: asyncpg.Pool, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = test_user["id"]
    async with test_pool.acquire() as conn:
        await user_consent_repository.record(conn, user_id, TERMS_VERSION)

    async def fake_get_pool() -> asyncpg.Pool:
        return test_pool

    monkeypatch.setattr(chat, "get_pool", fake_get_pool)
    monkeypatch.setattr(ws_auth, "verify_jwt", lambda token: {"sub": user_id})

    new_connection = uuid4()

    class TakenOverWebSocket(FakeWebSocket):
        async def receive_text(self) -> str:
            if not self._inbound:
                session_id = next(
                    json.loads(raw)["session_id"] for raw in self.sent if json.loads(raw)["type"] == "session_started"
                )
                async with test_pool.acquire() as conn:
                    await dialogue_session_repository.claim_connection(conn, session_id, user_id, new_connection)
            return await super().receive_text()

    inbound = [
        json.dumps({"type": "authenticate", "token": "x", "protocol_version": PROTOCOL_VERSION}),
        json.dumps({"type": "start_learning", "topic": "二分探索"}),
    ]
    ws = TakenOverWebSocket(FakeGraph(), inbound)

    await chat.websocket_chat(cast(Any, ws))

    session_id = next(json.loads(raw)["session_id"] for raw in ws.sent if json.loads(raw)["type"] == "session_started")
    async with test_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT status, connection_id FROM dialogue_sessions WHERE id = $1", session_id)
    assert row is not None
    assert row["status"] == "in_progress"
    assert row["connection_id"] == new_connection


@pytest.mark.asyncio(loop_scope="session")
async def test_llm_failure_then_disconnect_leaves_session_resumable(
    test_pool: asyncpg.Pool, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = test_user["id"]
    async with test_pool.acquire() as conn:
        await user_consent_repository.record(conn, user_id, TERMS_VERSION)

    async def fake_get_pool() -> asyncpg.Pool:
        return test_pool

    monkeypatch.setattr(chat, "get_pool", fake_get_pool)
    monkeypatch.setattr(ws_auth, "verify_jwt", lambda token: {"sub": user_id})

    graph = FakeGraph()
    graph.state_values = {
        "should_generate_note": False,
        "turn_count": 1,
        "messages": [HumanMessage(content="二分探索は半分に絞る手法です", id="pending-turn")],
    }
    start_stream = graph.astream

    async def astream_failing_on_turn(
        graph_input: Any, config: Any, stream_mode: str = "messages"
    ) -> AsyncIterator[tuple[AIMessageChunk, dict[str, Any]]]:
        if graph_input is None:
            raise RuntimeError("LLM boom")
        async for item in start_stream(graph_input, config, stream_mode):
            yield item

    graph.astream = astream_failing_on_turn  # type: ignore[method-assign]
    inbound = [
        json.dumps({"type": "authenticate", "token": "x", "protocol_version": PROTOCOL_VERSION}),
        json.dumps({"type": "start_learning", "topic": "二分探索"}),
        json.dumps(
            {"type": "user_message", "client_message_id": str(uuid4()), "content": "二分探索は半分に絞る手法です"}
        ),
    ]
    ws = FakeWebSocket(graph, inbound)

    await chat.websocket_chat(cast(Any, ws))

    sent = [json.loads(raw) for raw in ws.sent]
    session_id = next(msg["session_id"] for msg in sent if msg["type"] == "session_started")
    assert [msg["type"] for msg in sent[-2:]] == ["error", "pending_message_rolled_back"]
    assert sent[-1]["content"] == "二分探索は半分に絞る手法です"

    async with test_pool.acquire() as conn:
        status = await conn.fetchval("SELECT status FROM dialogue_sessions WHERE id = $1", session_id)
        roles = await conn.fetch(
            "SELECT role FROM dialogue_messages WHERE dialogue_session_id = $1 ORDER BY message_order", session_id
        )
    assert status == "disconnect"
    assert [r["role"] for r in roles] == ["user", "assistant"]


_CARD = {
    "questions": [
        {"key": "source", "header": "教材", "question": "q", "options": [{"label": "書籍"}], "multi_select": True}
    ]
}


async def _fetch_session_topic(session_id: UUID) -> str | None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        return cast(
            str | None, await conn.fetchval("SELECT topic FROM dialogue_sessions WHERE id = $1", str(session_id))
        )
    finally:
        await conn.close()


def test_start_learning_sends_and_persists_intake_card(ws_env: SimpleNamespace) -> None:
    ws_env.graph.stream_chunks = []
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 1,
        "topic": "React Hooks",
        "messages": [
            HumanMessage(content="仕事でReactのフックを使うので"),
            AIMessage(content="React Hooksを学ぶんですね。", additional_kwargs={"intake_card": _CARD}),
        ],
    }
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_learning", "topic": "仕事でReactのフックを使うので"})

        started = ws.receive_json()
        question = ws.receive_json()
        assert question["type"] == "intake_question"
        assert question["topic"] == "React Hooks"
        assert ws.receive_json()["type"] == "assistant_message_end"
        ws.send_text("not json")
        assert ws.receive_json()["type"] == "error"

    session_id = UUID(started["session_id"])
    rows = _run(_fetch_messages(session_id))
    assert rows[1]["content"] == "React Hooksを学ぶんですね。"
    assert json.loads(rows[1]["intake_card"])["questions"][0]["options"][0]["label"] == "書籍"
    assert _run(_fetch_session_topic(session_id)) == "React Hooks"


def test_intake_answers_are_attached_to_the_human_message(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)

        ws.send_json(
            {
                "type": "user_message",
                "client_message_id": str(uuid4()),
                "content": "教材: 書籍",
                "intake_answers": {"source": ["書籍"]},
            }
        )
        _drain_assistant_turn(ws)

    human = next(
        values["messages"][0]
        for values, _ in ws_env.graph.update_calls
        if values.get("messages") and isinstance(values["messages"][0], HumanMessage)
    )
    assert human.additional_kwargs["intake_answers"] == {
        "topic": "",
        "purpose": "",
        "source": ["書籍"],
        "prior_knowledge": "",
    }


def test_intake_answers_are_saved_with_the_user_message(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = _start_learning(ws)

        ws.send_json(
            {
                "type": "user_message",
                "client_message_id": str(uuid4()),
                "content": "教材: 書籍",
                "intake_answers": {"source": ["書籍"]},
            }
        )
        _drain_assistant_turn(ws)
        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "自由文の返信"})
        _drain_assistant_turn(ws)

    users = [r for r in _run(_fetch_messages(UUID(session_id))) if r["role"] == "user"]
    assert json.loads(users[-2]["intake_answers"]) == {
        "topic": "",
        "purpose": "",
        "source": ["書籍"],
        "prior_knowledge": "",
    }
    assert users[-1]["intake_answers"] is None


def test_cancel_of_intake_answers_is_rejected(ws_env: SimpleNamespace) -> None:
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 2,
        "messages": [
            HumanMessage(content="教材: 書籍", id="h1", additional_kwargs={"intake_answers": {"source": ["書籍"]}}),
            AIMessage(content="始めましょう", id="a1"),
        ],
    }
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "教材: 書籍"})
        _drain_assistant_turn(ws)

        ws.send_json({"type": "cancel_last_message"})
        res = ws.receive_json()

    assert res == {"type": "cancel_last_message_error", "detail": "聞き取りへの回答は取り消せません"}


def test_cancel_of_free_text_reply_to_intake_card_is_rejected(ws_env: SimpleNamespace) -> None:
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 2,
        "messages": [
            HumanMessage(content="Reactのフック", id="h0"),
            AIMessage(content="lead", id="a0", additional_kwargs={"intake_card": _CARD}),
            HumanMessage(content="仕事で使います", id="h1"),
            AIMessage(content="始めましょう", id="a1"),
        ],
    }
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "仕事で使います"})
        _drain_assistant_turn(ws)

        ws.send_json({"type": "cancel_last_message"})
        res = ws.receive_json()

    assert res == {"type": "cancel_last_message_error", "detail": "聞き取りへの回答は取り消せません"}


def test_resume_rolls_back_an_unanswered_card_answer_without_replaying_its_text(ws_env: SimpleNamespace) -> None:
    session_id = uuid4()
    _run(_insert_session(session_id, ws_env.user_id, graph_version=GRAPH_VERSION))
    _run(
        _insert_messages(session_id, [("user", "Reactのフック"), ("assistant", "lead"), ("user", "目的: 仕事で使う")])
    )
    pending = HumanMessage(content="目的: 仕事で使う", additional_kwargs={"intake_answers": {"purpose": "仕事で使う"}})
    pending.id = "pending-answers"
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 1,
        "messages": [HumanMessage(content="Reactのフック"), AIMessage(content="lead"), pending],
    }

    received = _resume_and_collect(ws_env, session_id)

    rolled_back = [m for m in received if m["type"] == "pending_message_rolled_back"]
    assert rolled_back == [{"type": "pending_message_rolled_back", "content": ""}]
    assert [r["role"] for r in _run(_fetch_messages(session_id))] == ["user", "assistant"]
    removals = [values for values, _ in ws_env.graph.update_calls if "messages" in values]
    assert removals and removals[0]["messages"][0].id == "pending-answers"


_CORRECTION_CARD = {"previous_topic": "この仕組み", "new_topic": "Linuxの仕組み"}


def _answer(content: str = "はい、トピックを変更する", answer: str = "accept", **extra: Any) -> HumanMessage:
    return HumanMessage(content=content, additional_kwargs={"topic_correction_answer": answer}, **extra)


def test_topic_correction_question_is_sent_and_persisted(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = _start_learning(ws)
        ws_env.graph.stream_chunks = []
        ws_env.graph.state_values = {
            "should_generate_note": False,
            "turn_count": 2,
            "topic": "この仕組み",
            "messages": [
                HumanMessage(content="Linuxの仕組みに変更して"),
                AIMessage(content="変更しますか？", additional_kwargs={"topic_correction_card": _CORRECTION_CARD}),
            ],
        }

        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "Linuxの仕組みに変更して"})
        question = ws.receive_json()
        assert question["type"] == "topic_correction_question"
        assert question["content"] == "変更しますか？"
        assert question["card"] == _CORRECTION_CARD
        assert ws.receive_json()["type"] == "assistant_message_end"
        _wait_until_handled(ws)

    rows = _run(_fetch_messages(UUID(session_id)))
    assert rows[-1]["content"] == "変更しますか？"
    assert json.loads(rows[-1]["topic_correction_card"]) == _CORRECTION_CARD


def _send_topic_correction_answer(ws_env: SimpleNamespace, *, pending: bool) -> tuple[HumanMessage, list[Any]]:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = _start_learning(ws)
        ws_env.graph.state_values = {
            "should_generate_note": False,
            "turn_count": 2,
            **({"pending_topic_correction": {"new_topic": "Linuxの仕組み"}} if pending else {}),
        }

        ws.send_json(
            {
                "type": "user_message",
                "client_message_id": str(uuid4()),
                "content": "はい、トピックを変更する",
                "topic_correction_answer": "accept",
            }
        )
        _drain_assistant_turn(ws)

    human = next(
        values["messages"][0]
        for values, _ in ws_env.graph.update_calls
        if values.get("messages") and isinstance(values["messages"][0], HumanMessage)
    )
    users = [r for r in _run(_fetch_messages(UUID(session_id))) if r["role"] == "user"]
    return human, users


def test_topic_correction_answer_is_attached_to_the_human_message_and_saved(ws_env: SimpleNamespace) -> None:
    human, users = _send_topic_correction_answer(ws_env, pending=True)

    assert human.additional_kwargs["topic_correction_answer"] == "accept"
    assert users[-1]["topic_correction_answer"] == "accept"


def test_topic_correction_answer_without_a_pending_correction_is_an_ordinary_message(
    ws_env: SimpleNamespace,
) -> None:
    human, users = _send_topic_correction_answer(ws_env, pending=False)

    assert "topic_correction_answer" not in human.additional_kwargs
    assert human.content == "はい、トピックを変更する"
    assert users[-1]["topic_correction_answer"] is None


def test_an_ordinary_message_does_not_read_the_graph_state_for_a_pending_correction(
    ws_env: SimpleNamespace,
) -> None:
    calls: list[str] = []
    original_get = ws_env.graph.aget_state
    original_update = ws_env.graph.aupdate_state

    async def recording_aget_state(config: Any) -> Any:
        calls.append("get")
        return await original_get(config)

    async def recording_aupdate_state(config: Any, values: dict[str, Any], as_node: str | None = None) -> None:
        calls.append("update")
        await original_update(config, values, as_node)

    ws_env.graph.aget_state = recording_aget_state
    ws_env.graph.aupdate_state = recording_aupdate_state
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        before = len(calls)
        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "ふつうの発言"})
        _drain_assistant_turn(ws)

    turn = calls[before:]
    assert "update" in turn
    assert "get" not in turn[: turn.index("update")]


def test_cancel_of_a_topic_correction_answer_is_rejected(ws_env: SimpleNamespace) -> None:
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 3,
        "messages": [_answer(id="h1"), AIMessage(content="切り替えました", id="a1")],
    }
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "はい"})
        _drain_assistant_turn(ws)

        ws.send_json({"type": "cancel_last_message"})
        res = ws.receive_json()

    assert res == {"type": "cancel_last_message_error", "detail": "トピックの変更への回答は取り消せません"}


def test_cancel_of_the_turn_that_asked_drops_the_pending_correction(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        ws_env.graph.stream_chunks = []
        ws_env.graph.state_values = {
            "should_generate_note": False,
            "turn_count": 3,
            "pending_topic_correction": {"new_topic": "Linuxの仕組み"},
            "messages": [
                HumanMessage(content="Linuxの仕組みに変更して", id="h1"),
                AIMessage(
                    content="変更しますか？", id="a1", additional_kwargs={"topic_correction_card": _CORRECTION_CARD}
                ),
            ],
        }
        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "Linuxの仕組みに変更して"})
        assert ws.receive_json()["type"] == "topic_correction_question"
        assert ws.receive_json()["type"] == "assistant_message_end"

        ws.send_json({"type": "cancel_last_message"})
        res = ws.receive_json()

    assert res["type"] == "cancel_last_message_success"
    cancel_update = next(values for values, _ in ws_env.graph.update_calls if "pending_topic_correction" in values)
    assert cancel_update["pending_topic_correction"] is None


def test_cancel_of_a_free_text_reply_to_a_topic_correction_question_is_rejected(ws_env: SimpleNamespace) -> None:
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 3,
        "messages": [
            HumanMessage(content="Linuxの仕組みに変更して", id="h0"),
            AIMessage(
                content="変更しますか？", id="a0", additional_kwargs={"topic_correction_card": _CORRECTION_CARD}
            ),
            HumanMessage(content="やっぱり続けます", id="h1"),
            AIMessage(content="続けましょう", id="a1"),
        ],
    }
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "やっぱり続けます"})
        _drain_assistant_turn(ws)

        ws.send_json({"type": "cancel_last_message"})
        res = ws.receive_json()

    assert res == {"type": "cancel_last_message_error", "detail": "トピックの変更への回答は取り消せません"}


def test_resume_rolls_back_an_unanswered_topic_correction_answer_without_replaying_its_text(
    ws_env: SimpleNamespace,
) -> None:
    session_id = uuid4()
    _run(_insert_session(session_id, ws_env.user_id, graph_version=GRAPH_VERSION))
    _run(_insert_messages(session_id, [("user", "二分探索"), ("assistant", "lead"), ("assistant", "変更しますか？")]))
    _run(_insert_messages_after(session_id, 4, "user", "はい、トピックを変更する"))
    pending = _answer()
    pending.id = "pending-answer"
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 1,
        "messages": [
            HumanMessage(content="二分探索"),
            AIMessage(content="変更しますか？", additional_kwargs={"topic_correction_card": _CORRECTION_CARD}),
            pending,
        ],
    }

    received = _resume_and_collect(ws_env, session_id)

    rolled_back = [m for m in received if m["type"] == "pending_message_rolled_back"]
    assert rolled_back == [{"type": "pending_message_rolled_back", "content": ""}]
    removals = [values for values, _ in ws_env.graph.update_calls if "messages" in values]
    assert removals and removals[0]["messages"][0].id == "pending-answer"


_EDITABLE = {
    "session_type": "learning",
    "should_generate_note": False,
    "turn_count": 3,
    "intake_complete": True,
    "depth_map": {"aspects": []},
    "topic": "二分探索",
}


def _edit_topic(ws: Any, topic: str = "Linuxの仕組み") -> None:
    ws.send_json(
        {
            "type": "user_message",
            "client_message_id": str(uuid4()),
            "content": f"トピックを「{topic}」に変更しました",
            "topic_edit": topic,
        }
    )


def test_a_topic_edit_is_attached_to_the_human_message_and_saved(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = _start_learning(ws)
        ws_env.graph.state_values = dict(_EDITABLE)
        _edit_topic(ws)
        _drain_assistant_turn(ws)

    human = next(
        values["messages"][0]
        for values, _ in ws_env.graph.update_calls
        if values.get("messages") and isinstance(values["messages"][0], HumanMessage)
    )
    assert human.additional_kwargs["topic_edit"] == "Linuxの仕組み"
    users = [r for r in _run(_fetch_messages(UUID(session_id))) if r["role"] == "user"]
    assert users[-1]["topic_edit"] == "Linuxの仕組み"


@pytest.mark.parametrize(
    "state",
    [
        {**_EDITABLE, "intake_complete": False},
        {**_EDITABLE, "depth_map": None},
        {**_EDITABLE, "topic": " linuxの仕組み "},
    ],
)
def test_a_topic_edit_that_cannot_apply_is_rejected_without_saving(
    ws_env: SimpleNamespace, state: dict[str, Any]
) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = _start_learning(ws)
        ws_env.graph.state_values = state
        _edit_topic(ws)
        res = ws.receive_json()

    assert res["type"] == "topic_edit_rejected"
    assert res["detail"]
    rows = _run(_fetch_messages(UUID(session_id)))
    assert [row["content"] for row in rows if row["role"] == "user"] == ["二分探索"]
    assert all(row["topic_edit"] is None for row in rows)
    assert not any(
        values.get("messages") and isinstance(values["messages"][0], HumanMessage)
        for values, _ in ws_env.graph.update_calls
    )


def test_cancel_of_a_topic_edit_is_rejected(ws_env: SimpleNamespace) -> None:
    ws_env.graph.state_values = {
        **_EDITABLE,
        "messages": [
            HumanMessage(
                content="トピックを「Linuxの仕組み」に変更しました",
                id="h1",
                additional_kwargs={"topic_edit": "Linuxの仕組み"},
            ),
            AIMessage(content="切り替えました", id="a1"),
        ],
    }
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        _edit_topic(ws)
        _drain_assistant_turn(ws)

        ws.send_json({"type": "cancel_last_message"})
        res = ws.receive_json()

    assert res == {"type": "cancel_last_message_error", "detail": "トピックの変更は取り消せません"}


def test_resume_rolls_back_an_unanswered_topic_edit_without_replaying_its_text(ws_env: SimpleNamespace) -> None:
    session_id = uuid4()
    _run(_insert_session(session_id, ws_env.user_id, graph_version=GRAPH_VERSION))
    _run(_insert_messages(session_id, [("user", "二分探索"), ("assistant", "lead"), ("assistant", "問い")]))
    _run(_insert_messages_after(session_id, 4, "user", "トピックを「Linuxの仕組み」に変更しました"))
    pending = HumanMessage(
        content="トピックを「Linuxの仕組み」に変更しました", additional_kwargs={"topic_edit": "Linuxの仕組み"}
    )
    pending.id = "pending-edit"
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 1,
        "messages": [HumanMessage(content="二分探索"), AIMessage(content="問い"), pending],
    }

    received = _resume_and_collect(ws_env, session_id)

    rolled_back = [m for m in received if m["type"] == "pending_message_rolled_back"]
    assert rolled_back == [{"type": "pending_message_rolled_back", "content": ""}]


def test_resume_rolls_back_a_db_only_topic_edit_without_replaying_its_text(ws_env: SimpleNamespace) -> None:
    session_id = uuid4()
    _run(_insert_session(session_id, ws_env.user_id, graph_version=GRAPH_VERSION))
    _run(_insert_messages(session_id, [("user", "二分探索"), ("assistant", "lead"), ("assistant", "問い")]))
    _run(_insert_topic_edit_after(session_id, 4, "Linuxの仕組み"))
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 1,
        "messages": [HumanMessage(content="二分探索"), AIMessage(content="問い")],
    }

    received = _resume_and_collect(ws_env, session_id)

    rolled_back = [m for m in received if m["type"] == "pending_message_rolled_back"]
    assert rolled_back == [{"type": "pending_message_rolled_back", "content": ""}]


async def _insert_collection_with_synthesis(user_id: str, connections: list[dict[str, Any]]) -> UUID:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        collection_id = await conn.fetchval(
            "INSERT INTO note_collections (user_id, name) VALUES ($1, 'Linuxのしくみ') RETURNING id", user_id
        )
        for topic in ("プロセス", "システムコール"):
            await conn.execute(
                "INSERT INTO notes (id, user_id, topic, content, summary, collection_id) "
                "VALUES ($1, $2, $3, '本文', '要約', $4)",
                uuid4(),
                user_id,
                topic,
                collection_id,
            )
        await conn.execute(
            "INSERT INTO collection_syntheses "
            "(collection_id, content, connections, contradictions, gaps, source_notes) "
            "VALUES ($1, 'まとめ', $2::jsonb, '[]', '[]', '[]')",
            collection_id,
            json.dumps(connections),
        )
        return cast(UUID, collection_id)
    finally:
        await conn.close()


async def _count_sessions() -> int:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        return cast(int, await conn.fetchval("SELECT COUNT(*) FROM dialogue_sessions"))
    finally:
        await conn.close()


_CONNECTION = {"id": "c1", "title": "t", "note_ids": [], "explanation": "e", "question": "q"}


def test_start_synthesis_without_collection_returns_error(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_synthesis", "collection_id": str(uuid4())})

        err = ws.receive_json()
        assert err == {"type": "error", "code": "collection_not_found", "detail": "まとめノートが見つかりません"}


def test_start_synthesis_without_connections_returns_error_and_creates_no_session(ws_env: SimpleNamespace) -> None:
    collection_id = _run(_insert_collection_with_synthesis(ws_env.user_id, []))
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_synthesis", "collection_id": str(collection_id)})

        assert ws.receive_json() == {
            "type": "error",
            "code": "no_synthesis_connections",
            "detail": "まとめの対象になるつながりがありません",
        }
    assert _run(_count_sessions()) == 0


def test_start_synthesis_streams_the_first_question(ws_env: SimpleNamespace) -> None:
    collection_id = _run(_insert_collection_with_synthesis(ws_env.user_id, [_CONNECTION]))
    ws_env.graph.stream_chunks = [("1つ目の問い", "synthesis_start")]
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_synthesis", "collection_id": str(collection_id)})

        started = ws.receive_json()
        assert started["type"] == "session_started"
        assert started["session_type"] == "synthesis"
        assert ws.receive_json() == {"type": "assistant_message_chunk", "content": "1つ目の問い"}
        assert ws.receive_json()["type"] == "assistant_message_end"

    session = _run(_fetch_session(UUID(started["session_id"])))
    assert session is not None
    assert session["collection_id"] == collection_id
    assert session["topic"] == "Linuxのしくみ"


def test_start_synthesis_leaves_an_in_progress_learning_session_untouched(ws_env: SimpleNamespace) -> None:
    learning_id = uuid4()
    _run(_insert_session(learning_id, ws_env.user_id, GRAPH_VERSION))
    collection_id = _run(_insert_collection_with_synthesis(ws_env.user_id, [_CONNECTION]))
    ws_env.graph.stream_chunks = [("1つ目の問い", "synthesis_start")]
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_synthesis", "collection_id": str(collection_id)})
        assert ws.receive_json()["type"] == "session_started"
        _drain_assistant_turn(ws)

    learning = _run(_fetch_session(learning_id))
    assert learning is not None
    assert learning["status"] == "in_progress"


def test_end_synthesis_session_finishes_from_the_dialogue_node(ws_env: SimpleNamespace) -> None:
    collection_id = _run(_insert_collection_with_synthesis(ws_env.user_id, [_CONNECTION]))
    ws_env.graph.stream_chunks = [("1つ目の問い", "synthesis_start")]
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_synthesis", "collection_id": str(collection_id)})
        assert ws.receive_json()["type"] == "session_started"
        _drain_assistant_turn(ws)

        ws_env.graph.state_values = {"session_type": "synthesis"}
        ws.send_json({"type": "end_session"})
        assert ws.receive_json()["type"] == "session_ended"

    assert ({"should_generate_note": True}, "synthesis_dialogue") in ws_env.graph.update_calls


def test_offered_turn_carries_the_end_confirmation(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        ws_env.graph.state_values = {**_MAP_WITH_CONTENT, "end_confirmation": "offered"}
        _send(ws, "今日はここまでにします")
        assert ws.receive_json()["type"] == "assistant_message_chunk"
        end = ws.receive_json()
        assert end["type"] == "assistant_message_end"
        assert end["end_confirmation"] == {"creates_note": True}


def test_offered_turn_without_explanation_says_no_note(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        ws_env.graph.state_values = {**_MAP_WITH_CONTENT, "map_covered": [], "end_confirmation": "offered"}
        _send(ws, "終わります")
        ws.receive_json()
        assert ws.receive_json()["end_confirmation"] == {"creates_note": False}


def test_confirmed_turn_ends_through_the_end_session_path(ws_env: SimpleNamespace) -> None:
    release = threading.Event()

    async def _held_until_released(graph_input: Any, config: Any = None) -> dict[str, Any]:
        while not release.is_set():
            await asyncio.sleep(0.01)
        return {}

    ws_env.graph.ainvoke = _held_until_released
    try:
        with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
            _authenticate(ws)
            session_id = _start_learning(ws)
            ws_env.graph.stream_chunks = []
            ws_env.graph.state_values = {**_MAP_WITH_CONTENT, "end_confirmation": "confirmed"}
            _send(ws, "はい、終わります")
            assert ws.receive_json()["type"] == "assistant_message_end"
            ended = ws.receive_json()
            assert ended == {"type": "session_ended", "session_id": session_id, "note_skipped": False}
            assert _run(_session_status(UUID(session_id))) == "generate_note"
    finally:
        release.set()

    assert ({"should_generate_note": True}, "learning_dialogue") in ws_env.graph.update_calls


def test_confirmed_turn_saves_no_assistant_row(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = _start_learning(ws)
        ws_env.graph.stream_chunks = []
        ws_env.graph.state_values = {**_MAP_WITH_CONTENT, "end_confirmation": "confirmed"}
        _send(ws, "はい、終わります")
        ws.receive_json()
        ws.receive_json()

    roles = [r["role"] for r in _run(_fetch_messages(UUID(session_id)))]
    assert roles == ["user", "assistant", "user"]


def test_end_session_without_explanation_skips_the_note(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = _start_learning(ws)
        ws_env.graph.state_values = {"session_type": "learning", "intake_complete": False}
        ws.send_json({"type": "end_session"})
        assert ws.receive_json() == {"type": "session_ended", "session_id": None, "note_skipped": True}

    assert not any(values.get("should_generate_note") for values, _ in ws_env.graph.update_calls)
    assert _run(_session_status(UUID(session_id))) == "completed"


def _end_review(ws_env: SimpleNamespace, *, answered: bool) -> tuple[dict[str, Any], UUID]:
    note_id = _run(_insert_note(ws_env.user_id))
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_review", "note_id": str(note_id)})
        started = ws.receive_json()
        assert started["type"] == "session_started"
        assert ws.receive_json()["type"] == "assistant_message_chunk"
        assert ws.receive_json()["type"] == "assistant_message_end"
        ws_env.graph.state_values = {
            "session_type": "review",
            "review_answered": answered,
            "should_generate_note": False,
            "turn_count": 1,
        }
        ws.send_json({"type": "end_session"})
        return ws.receive_json(), UUID(started["session_id"])


def test_ending_an_unanswered_review_skips_the_note_update(ws_env: SimpleNamespace) -> None:
    ended, _ = _end_review(ws_env, answered=False)
    assert ended == {"type": "session_ended", "session_id": None, "note_skipped": True}
    assert not any(values.get("should_generate_note") for values, _ in ws_env.graph.update_calls)


def test_ending_an_answered_review_updates_the_note(ws_env: SimpleNamespace) -> None:
    ended, session_id = _end_review(ws_env, answered=True)
    assert ended == {"type": "session_ended", "session_id": str(session_id), "note_skipped": False}
    assert any(values.get("should_generate_note") for values, _ in ws_env.graph.update_calls)


def test_should_generate_note_from_the_graph_no_longer_ends_the_session(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = _start_learning(ws)
        ws_env.graph.state_values = {**_MAP_WITH_CONTENT, "should_generate_note": True}
        _send(ws, "十分に説明できました")
        _drain_assistant_turn(ws)
        assert _run(_session_status(UUID(session_id))) == "in_progress"
        ws.send_json({"type": "end_session"})
        assert ws.receive_json() == {"type": "session_ended", "session_id": session_id, "note_skipped": False}


def test_cancel_clears_the_end_confirmation(ws_env: SimpleNamespace) -> None:
    ws_env.graph.state_values = {
        **_MAP_WITH_CONTENT,
        "turn_count": 2,
        "end_confirmation": "offered",
        "messages": [HumanMessage(content="終わります", id="h1"), AIMessage(content="下のボタンで", id="a1")],
    }
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        _send(ws, "終わります")
        _drain_assistant_turn(ws)
        ws.send_json({"type": "cancel_last_message"})
        assert ws.receive_json()["type"] == "cancel_last_message_success"

    cancel_update = ws_env.graph.update_calls[-1][0]
    assert cancel_update["end_confirmation"] is None


def test_resume_restores_the_end_confirmation(ws_env: SimpleNamespace) -> None:
    session_id = uuid4()
    _run(_insert_session(session_id, ws_env.user_id, GRAPH_VERSION))
    ws_env.graph.state_values = {**_MAP_WITH_CONTENT, "end_confirmation": "offered", "messages": []}
    received = _resume_and_collect(ws_env, session_id)
    resumed = next(m for m in received if m["type"] == "session_resumed")
    assert resumed["end_confirmation"] == {"creates_note": True}


def test_unconfirmed_turn_with_empty_content_still_saves_an_assistant_row(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        session_id = _start_learning(ws)
        ws_env.graph.stream_chunks = []
        ws_env.graph.state_values = {**_MAP_WITH_CONTENT, "end_confirmation": None}
        _send(ws, "説明します")
        assert ws.receive_json()["type"] == "assistant_message_end"
        _wait_until_handled(ws)

    roles = [r["role"] for r in _run(_fetch_messages(UUID(session_id)))]
    assert roles == ["user", "assistant", "user", "assistant"]


_EXPLORE_MAP = {
    "topic": "二分探索",
    "aspects": [
        {
            "id": "比較",
            "name": "真ん中との比較",
            "is_core": True,
            "defined_question": "d",
            "reasoned_question": "r",
            "applied_question": "a",
        }
    ],
}


def _explore_values(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "session_type": "explore",
        "should_generate_note": False,
        "turn_count": 2,
        "topic": "二分探索",
        "explore_questions": [{"question": "二分探索とは", "answer_message_id": "a1"}],
        "messages": [
            HumanMessage(content="二分探索って何？"),
            AIMessage(content="答えです", id="a1"),
        ],
    }
    values.update(overrides)
    return values


def _start_explore(ws_env: SimpleNamespace, ws: Any) -> None:
    ws_env.graph.state_values = {
        "session_type": "explore",
        "should_generate_note": False,
        "turn_count": 1,
        "topic": "二分探索",
        "messages": [HumanMessage(content="二分探索って何？"), AIMessage(content="答えです")],
    }
    ws_env.graph.stream_chunks = [("答えです", "explore_start")]
    ws.send_json({"type": "start_explore", "topic": "二分探索って何？"})
    for _ in range(3):
        ws.receive_json()


def test_start_explore_creates_an_explore_session(ws_env: SimpleNamespace) -> None:
    ws_env.graph.state_values = {
        "session_type": "explore",
        "should_generate_note": False,
        "turn_count": 1,
        "topic": "二分探索",
        "messages": [HumanMessage(content="二分探索って何？"), AIMessage(content="答えです")],
    }
    ws_env.graph.stream_chunks = [("答えです", "explore_start")]
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_explore", "topic": "二分探索って何？"})
        started = ws.receive_json()
        chunk = ws.receive_json()
        end = ws.receive_json()

    assert started["session_type"] == "explore"
    assert "topic" not in started
    assert "first_message" not in started
    assert chunk == {"type": "assistant_message_chunk", "content": "答えです"}
    assert end["type"] == "assistant_message_end"
    assert ws_env.graph.stream_inputs[0]["session_type"] == "explore"
    session = _run(_fetch_session(UUID(started["session_id"])))
    assert session is not None
    assert session["session_type"] == "explore"


def test_explore_start_saves_the_topic_from_the_first_turn(ws_env: SimpleNamespace) -> None:
    ws_env.graph.stream_chunks = [("答えです", "explore_start")]
    ws_env.graph.state_values = {
        "session_type": "explore",
        "should_generate_note": False,
        "turn_count": 1,
        "topic": "二分探索",
        "messages": [HumanMessage(content="二分探索って何？"), AIMessage(content="答えです")],
    }
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_explore", "topic": "二分探索って何？"})
        started = ws.receive_json()
        assert ws.receive_json() == {"type": "assistant_message_chunk", "content": "答えです"}
        end = ws.receive_json()
        ws.send_text("not json")
        assert ws.receive_json()["type"] == "error"

    assert end["topic"] == "二分探索"
    assert "explore_overview" not in end
    session = _run(_fetch_session(UUID(started["session_id"])))
    assert session is not None
    assert session["topic"] == "二分探索"


def test_learning_start_keeps_its_topic_saving_as_before(ws_env: SimpleNamespace) -> None:
    ws_env.graph.state_values = {"should_generate_note": False, "turn_count": 1, "topic": "正規化した名前"}
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        started_id = _start_learning(ws, "二分探索")
        ws.send_text("not json")
        assert ws.receive_json()["type"] == "error"

    session = _run(_fetch_session(UUID(started_id)))
    assert session is not None
    assert session["topic"] is None


def _cancel_in_explore(ws_env: SimpleNamespace, messages: list[Any]) -> dict[str, Any]:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_explore(ws_env, ws)
        ws_env.graph.state_values = _explore_values(turn_count=3, messages=messages)
        ws_env.graph.stream_chunks = []
        _send(ws, "再送")
        while ws.receive_json()["type"] != "assistant_message_end":
            pass
        ws.send_json({"type": "cancel_last_message"})
        res: dict[str, Any] = ws.receive_json()
    return res


def test_cancel_of_a_dialogue_turn_in_explore_is_allowed(ws_env: SimpleNamespace) -> None:
    res = _cancel_in_explore(
        ws_env,
        [
            HumanMessage(content="二分探索って何？", id="h1"),
            AIMessage(content="答えです", id="a1"),
            HumanMessage(content="なぜ並べるの？", id="h2"),
            AIMessage(content="説明", id="a2"),
        ],
    )

    assert res["type"] == "cancel_last_message_success"
    assert res["cancelled_content"] == "なぜ並べるの？"


def test_resume_explore_restores_an_explore_session(ws_env: SimpleNamespace) -> None:
    session_id = uuid4()
    _run(_insert_session(session_id, ws_env.user_id, graph_version=GRAPH_VERSION))
    _run(_set_session_type(session_id, "explore"))
    _run(_insert_messages(session_id, [("user", "二分探索って何？"), ("assistant", "答えです")]))
    ws_env.graph.state_values = _explore_values()

    received = _resume_and_collect(ws_env, session_id)

    resumed = next(m for m in received if m["type"] == "session_resumed")
    assert resumed["session_type"] == "explore"
    assert "explore_overview" not in resumed
    assert resumed["progress"] is None


def test_ending_an_explore_session_without_content_skips_the_memo(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_explore(ws_env, ws)
        ws_env.graph.state_values = _explore_values(explore_terms=[], explore_questions=[])

        ws.send_json({"type": "end_session"})
        ended = ws.receive_json()

    assert ended == {"type": "session_ended", "session_id": None, "note_skipped": True}


def test_ending_an_explore_session_with_content_generates_the_memo(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_explore(ws_env, ws)
        ws_env.graph.state_values = _explore_values()

        ws.send_json({"type": "end_session"})
        ended = ws.receive_json()

    assert ended["type"] == "session_ended"
    assert ended["note_skipped"] is False
    assert ws_env.graph.update_calls[-1] == ({"should_generate_note": True}, "explore_dialogue")


async def _insert_study_memo(
    user_id: str, topic: str = "二分探索", source: str = "入門書", depth_map: dict[str, Any] | None = None
) -> UUID:
    session_id = uuid4()
    await _insert_session(session_id, user_id, graph_version=GRAPH_VERSION)
    await _set_session_type(session_id, "explore")
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        return await study_memo_repository.insert(
            conn,
            user_id=user_id,
            dialogue_session_id=session_id,
            topic=topic,
            source=source,
            summary="",
            overview=[],
            glossary=[
                {"term": "計算量", "reading": "けいさんりょう", "meaning": "処理にかかる手間の目安"},
                {"term": "添字", "reading": "", "meaning": "要素の位置を表す番号"},
            ],
            questions=[],
            depth_map=_EXPLORE_MAP if depth_map is None else depth_map,
        )
    finally:
        await conn.close()


def test_start_learning_from_a_study_memo_seeds_the_state_and_stores_the_link(ws_env: SimpleNamespace) -> None:
    memo_id = _run(_insert_study_memo(ws_env.user_id))
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json(
            {"type": "start_learning", "topic": "クライアントが送ったトピック", "study_memo_id": str(memo_id)}
        )
        started = ws.receive_json()
        ws.receive_json()
        ws.receive_json()

    state = ws_env.graph.stream_inputs[0]
    assert state["topic"] == "二分探索"
    assert state["study_memo_id"] == str(memo_id)
    assert state["memo_depth_map"] == _EXPLORE_MAP
    assert state["memo_terms"] == [
        {"term": "計算量", "reading": "けいさんりょう"},
        {"term": "添字", "reading": ""},
    ]
    assert state["learning_source"] == "入門書"
    session = _run(_fetch_session(UUID(started["session_id"])))
    assert session is not None
    assert session["study_memo_id"] == memo_id
    assert session["topic"] == "二分探索"
    messages = _run(_fetch_messages(UUID(started["session_id"])))
    assert messages[0]["content"] == "二分探索"


def test_a_study_memo_without_aspects_starts_the_normal_intake(ws_env: SimpleNamespace) -> None:
    memo_id = _run(_insert_study_memo(ws_env.user_id, depth_map={"topic": "二分探索", "aspects": []}))
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_learning", "topic": "x", "study_memo_id": str(memo_id)})
        started = ws.receive_json()
        ws.receive_json()
        ws.receive_json()

    state = ws_env.graph.stream_inputs[0]
    assert "memo_depth_map" not in state
    assert state["memo_terms"]
    assert state["study_memo_id"] == str(memo_id)
    assert state["topic"] == "二分探索"
    session = _run(_fetch_session(UUID(started["session_id"])))
    assert session is not None
    assert session["study_memo_id"] == memo_id


def test_a_study_memo_of_another_user_is_ignored(ws_env: SimpleNamespace) -> None:
    other_user = "someone-else"
    _run(_setup_user(other_user))
    memo_id = _run(_insert_study_memo(other_user))
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_learning", "topic": "二分探索を学びたい", "study_memo_id": str(memo_id)})
        started = ws.receive_json()
        ws.receive_json()
        ws.receive_json()

    state = ws_env.graph.stream_inputs[0]
    assert state["topic"] == "二分探索を学びたい"
    assert not {"study_memo_id", "memo_depth_map", "memo_terms"} & set(state)
    session = _run(_fetch_session(UUID(started["session_id"])))
    assert session is not None
    assert session["study_memo_id"] is None


def test_an_unknown_study_memo_is_ignored(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_learning", "topic": "二分探索", "study_memo_id": str(uuid4())})
        ws.receive_json()
        ws.receive_json()
        ws.receive_json()

    assert "memo_depth_map" not in ws_env.graph.stream_inputs[0]


def test_a_study_memo_wins_over_the_trial_flag(ws_env: SimpleNamespace) -> None:
    memo_id = _run(_insert_study_memo(ws_env.user_id))
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_learning", "topic": "x", "trial": True, "study_memo_id": str(memo_id)})
        ws.receive_json()
        ws.receive_json()
        ws.receive_json()

    assert "trial" not in ws_env.graph.stream_inputs[0]


def test_the_memo_kickoff_is_sent_as_one_chunk(ws_env: SimpleNamespace) -> None:
    memo_id = _run(_insert_study_memo(ws_env.user_id))
    ws_env.graph.stream_chunks = []
    ws_env.graph.state_values = {
        "should_generate_note": False,
        "turn_count": 1,
        "topic": "二分探索",
        "messages": [
            HumanMessage(content="二分探索"),
            AIMessage(content="教わった内容を説明してみましょう", additional_kwargs={"memo_kickoff": True}),
        ],
    }
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_learning", "topic": "二分探索", "study_memo_id": str(memo_id)})
        ws.receive_json()
        chunk = ws.receive_json()
        end = ws.receive_json()

    assert chunk == {"type": "assistant_message_chunk", "content": "教わった内容を説明してみましょう"}
    assert end["type"] == "assistant_message_end"


_OTHER_USER = "ws-other-user"


def test_resuming_another_users_session_is_rejected_and_leaves_it_untouched(ws_env: SimpleNamespace) -> None:
    _run(_setup_user(_OTHER_USER))
    session_id = uuid4()
    _run(_insert_session(session_id, _OTHER_USER, GRAPH_VERSION))
    _run(_insert_messages(session_id, [("user", "二分探索"), ("assistant", "どうぞ"), ("user", "未回答")]))

    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "resume_session", "session_id": str(session_id)})
        err = ws.receive_json()
        _send(ws, "続きです")
        after = ws.receive_json()

    assert err == {
        "type": "error",
        "code": "session_not_found",
        "detail": "セッションが見つかりません。新しく始めてください",
    }
    assert after["detail"] == "セッションが開始されていません。ページを再読み込みしてください"
    assert ws_env.graph.update_calls == []
    assert _run(_session_status(session_id)) == "in_progress"
    assert len(_run(_fetch_messages(session_id))) == 3


def test_starting_a_review_of_another_users_note_is_rejected(ws_env: SimpleNamespace) -> None:
    _run(_setup_user(_OTHER_USER))
    note_id = _run(_insert_note(_OTHER_USER))

    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_review", "note_id": str(note_id)})
        err = ws.receive_json()

    assert err == {"type": "error", "code": "note_not_found", "detail": "ノートが見つかりません"}
    assert ws_env.graph.stream_inputs == []
    assert _run(_count_sessions()) == 0


def test_starting_a_synthesis_of_another_users_collection_is_rejected(ws_env: SimpleNamespace) -> None:
    _run(_setup_user(_OTHER_USER))
    collection_id = _run(_insert_collection_with_synthesis(_OTHER_USER, [_CONNECTION]))

    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_synthesis", "collection_id": str(collection_id)})
        err = ws.receive_json()

    assert err == {"type": "error", "code": "collection_not_found", "detail": "まとめノートが見つかりません"}
    assert ws_env.graph.stream_inputs == []
    assert _run(_count_sessions()) == 0


@pytest.mark.parametrize(
    "authenticate",
    [
        {"type": "authenticate", "token": "x"},
        {"type": "authenticate", "token": "x", "protocol_version": PROTOCOL_VERSION + 1},
        {"type": "authenticate", "token": "x", "protocol_version": str(PROTOCOL_VERSION)},
    ],
)
async def test_another_protocol_version_is_answered_with_the_same_error_until_it_disconnects(
    authenticate: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def no_pool() -> asyncpg.Pool:
        raise AssertionError("版が合わない接続はセッションに触れない")

    monkeypatch.setattr(chat, "get_pool", no_pool)
    monkeypatch.setattr(ws_auth, "verify_jwt", lambda token: {"sub": "user-1"})
    ws = FakeWebSocket(
        FakeGraph(),
        [json.dumps(authenticate), json.dumps({"type": "start_learning", "topic": "二分探索"})],
    )

    await chat.websocket_chat(cast(Any, ws))

    sent = [json.loads(raw) for raw in ws.sent]
    assert len(sent) == 2
    for msg in sent:
        assert msg["type"] == "error"
        assert msg["code"] == "protocol_version_mismatch"
        assert "再読み込み" in msg["detail"]


async def _withdraw_consent(user_id: str) -> None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute("DELETE FROM user_consents WHERE user_id = $1", user_id)
    finally:
        await conn.close()


def test_a_user_without_consent_is_answered_with_consent_required_and_no_session_starts(
    ws_env: SimpleNamespace,
) -> None:
    _run(_withdraw_consent(ws_env.user_id))

    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        first = ws.receive_json()
        ws.send_json({"type": "start_learning", "topic": "二分探索"})
        second = ws.receive_json()

    for msg in (first, second):
        assert msg["type"] == "error"
        assert msg["code"] == "consent_required"
    assert ws_env.graph.stream_inputs == []
    assert _run(_count_sessions()) == 0


async def _count_explore_sessions() -> int:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        return cast(int, await conn.fetchval("SELECT count(*) FROM dialogue_sessions WHERE session_type = 'explore'"))
    finally:
        await conn.close()


async def _first_user_message(session_id: UUID) -> str:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        return cast(
            str,
            await conn.fetchval(
                "SELECT content FROM dialogue_messages"
                " WHERE dialogue_session_id = $1 AND role = 'user' ORDER BY message_order",
                str(session_id),
            ),
        )
    finally:
        await conn.close()


def _explore_source(note_id: UUID, feedback_id: UUID, index: int = 0) -> dict[str, Any]:
    return {"note_id": str(note_id), "feedback_id": str(feedback_id), "improvement_index": index}


def test_start_explore_from_an_improvement_uses_the_note_topic(ws_env: SimpleNamespace) -> None:
    note_id = _run(_insert_note(ws_env.user_id, topic="二分探索", aspect_map=json.dumps(_FOCUS_MAP)))
    feedback_id = _run(_insert_feedback(note_id, ws_env.user_id, "計算量の見積もり", _FOCUS_ITEMS[:1]))
    ws_env.graph.stream_chunks = [("答えです", "explore_start")]
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_explore", "topic": "", "source": _explore_source(note_id, feedback_id)})
        started = ws.receive_json()
        ws.receive_json()
        ws.receive_json()

    assert started["topic"] == "二分探索"
    assert started["first_message"] == "改善点「計算量の見積もり」を理解したい"
    session_id = UUID(started["session_id"])
    assert _run(_fetch_session_topic(session_id)) == "二分探索"
    assert _run(_first_user_message(session_id)) == "改善点「計算量の見積もり」を理解したい"
    initial = ws_env.graph.stream_inputs[0]
    assert initial["topic"] == "二分探索"
    assert initial["explore_gap"]["improvement"] == "計算量の見積もり"
    assert initial["explore_gap"]["aspect_name"] == "計算量"


def test_start_explore_from_another_users_note_is_rejected(ws_env: SimpleNamespace) -> None:
    other_user = "someone-else"
    _run(_setup_user(other_user))
    note_id = _run(_insert_note(other_user))
    feedback_id = _run(_insert_feedback(note_id, other_user, "計算量の見積もり", _FOCUS_ITEMS[:1]))
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_explore", "topic": "", "source": _explore_source(note_id, feedback_id)})
        err = ws.receive_json()

    assert err["type"] == "error"
    assert err["code"] == "note_not_found"
    assert _run(_count_explore_sessions()) == 0


def test_start_explore_from_a_stale_feedback_is_rejected(ws_env: SimpleNamespace) -> None:
    note_id = _run(_insert_note(ws_env.user_id))
    old_feedback_id = _run(_insert_feedback(note_id, ws_env.user_id, "計算量の見積もり", _FOCUS_ITEMS[:1]))
    _run(_insert_feedback(note_id, ws_env.user_id, "ソート済みの前提", _FOCUS_ITEMS[1:2]))
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_explore", "topic": "", "source": _explore_source(note_id, old_feedback_id)})
        err = ws.receive_json()

    assert err["type"] == "error"
    assert err["code"] == "improvement_not_found"
    assert _run(_count_explore_sessions()) == 0


def _review_progress(status: str, **extra: Any) -> dict[str, Any]:
    return {
        "review_points": [{"id": "p1", "status": status}, {"id": "p2", "status": "pending"}],
        "review_current_point_id": "p1",
        **extra,
    }


def test_note_peek_available_when_current_point_is_hinted(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        ws_env.graph.state_values = _review_progress("hinted")
        _send(ws, "半分に絞る？")
        ws.receive_json()
        assert ws.receive_json()["note_peek_available"] is True


def test_note_peek_unavailable_when_current_point_is_pending(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        ws_env.graph.state_values = _review_progress("pending")
        _send(ws, "半分に絞ります")
        ws.receive_json()
        assert ws.receive_json()["note_peek_available"] is False


def test_note_peek_unavailable_while_end_is_offered(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        ws_env.graph.state_values = _review_progress("hinted", end_confirmation="offered")
        _send(ws, "終わります")
        ws.receive_json()
        assert ws.receive_json()["note_peek_available"] is False


def test_note_peek_unavailable_without_review_points(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)
        ws_env.graph.state_values = {"review_points": None, "review_current_point_id": None}
        _send(ws, "半分に絞ります")
        ws.receive_json()
        assert ws.receive_json()["note_peek_available"] is False


def test_resumed_review_reports_note_peek_available(ws_env: SimpleNamespace) -> None:
    session_id = uuid4()
    _run(_insert_session(session_id, ws_env.user_id, GRAPH_VERSION))
    ws_env.graph.state_values = {**_MAP_WITH_CONTENT, **_review_progress("hinted"), "messages": []}
    received = _resume_and_collect(ws_env, session_id)
    resumed = next(m for m in received if m["type"] == "session_resumed")
    assert resumed["note_peek_available"] is True


async def test_cancel_reports_note_peek_available_of_restored_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    earlier = [
        HumanMessage(content="ノート", id="h0"),
        AIMessage(content="覚えていることは？", id="a0"),
        HumanMessage(content="足りない答え", id="h1"),
        AIMessage(content="ヒント", id="a1"),
    ]
    cancelled = [HumanMessage(content="2 回目の答え", id="h2"), AIMessage(content="正しい説明", id="a2")]
    after = {"messages": [*earlier, *cancelled], "turn_count": 3, **_review_progress("not_explained")}
    after["review_current_point_id"] = "p2"
    before = {"messages": earlier, "turn_count": 2, **_review_progress("hinted")}
    graph = _HistoryGraph(after, [after, before])

    deps = await _cancel_with(graph, monkeypatch)

    sent = json.loads(deps.websocket.sent[-1])
    assert sent["type"] == "cancel_last_message_success"
    assert sent["note_peek_available"] is True
