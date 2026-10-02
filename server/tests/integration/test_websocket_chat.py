import asyncio
import json
import os
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
from graph.version import GRAPH_VERSION

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://learning_optimizer:localdev@localhost:5433/learning_optimizer_test",
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

    async def astream(
        self, graph_input: Any, config: Any, stream_mode: str = "messages"
    ) -> AsyncIterator[tuple[AIMessageChunk, dict[str, Any]]]:
        for content, node in self.stream_chunks:
            yield AIMessageChunk(content=content), {"langgraph_node": node}

    async def ainvoke(self, graph_input: Any, config: Any = None) -> dict[str, Any]:
        return self.ainvoke_result

    async def aget_state(self, config: Any) -> SimpleNamespace:
        return SimpleNamespace(values=self.state_values)

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
    finally:
        await conn.close()


async def _truncate() -> None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute("TRUNCATE feedbacks, review_schedules, dialogue_messages, dialogue_sessions, notes CASCADE")
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


async def _insert_note(user_id: str, topic: str = "統計学") -> UUID:
    note_id = uuid4()
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute(
            "INSERT INTO notes (id, user_id, topic, content, summary, status) "
            "VALUES ($1, $2, $3, 'content', 'summary', 'active')",
            str(note_id),
            user_id,
            topic,
        )
    finally:
        await conn.close()
    return note_id


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


async def _fetch_messages(session_id: UUID) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        return await conn.fetch(
            "SELECT role, content, message_order, intake_card FROM dialogue_messages "
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


def _authenticate(ws: Any) -> None:
    ws.send_json({"type": "authenticate", "token": "x"})


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


def test_start_review_without_note_returns_error(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "start_review", "note_id": str(uuid4())})

        err = ws.receive_json()
        assert err["type"] == "error"
        assert "Note not found" in err["detail"]


def test_user_message_without_session_returns_error(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "こんにちは"})

        err = ws.receive_json()
        assert err["type"] == "error"
        assert "Session not started" in err["detail"]


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
        "progress": {"reached_aspects": ["計算量"], "target_count": 3, "is_complete": False, "aspects": []},
    }


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
        assert ws.receive_json() == {"type": "assistant_message_end", "progress": None}

        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "復習の回答です"})
        assert ws.receive_json()["type"] == "assistant_message_chunk"
        assert ws.receive_json() == {"type": "assistant_message_end", "progress": None}


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
    removals = [values for values, _ in ws_env.graph.update_calls if isinstance(values["messages"][0], RemoveMessage)]
    assert removals and removals[-1]["messages"][0].id == "pending-turn"

    session = _run(_fetch_session(session_id))
    assert session is not None
    assert session["status"] == "in_progress"


def test_session_ends_when_generation_triggered(ws_env: SimpleNamespace) -> None:
    ws_env.graph.state_values = {"should_generate_note": True, "turn_count": 3, "note_id": None}

    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)

        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "十分に説明できました"})
        _drain_assistant_turn(ws)
        assert ws.receive_json()["type"] == "session_ended"


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
        assert "Session not started" in res["detail"]


def test_cancel_before_first_turn_returns_error(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)

        ws.send_json({"type": "cancel_last_message"})
        res = ws.receive_json()
        assert res["type"] == "cancel_last_message_error"
        assert "No cancellable message" in res["detail"]


def test_cancel_after_session_ended_returns_error(ws_env: SimpleNamespace) -> None:
    ws_env.graph.state_values = {"should_generate_note": True, "turn_count": 3, "note_id": None}

    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)

        ws.send_json({"type": "user_message", "client_message_id": str(uuid4()), "content": "十分に説明できました"})
        _drain_assistant_turn(ws)
        assert ws.receive_json()["type"] == "session_ended"

        ws.send_json({"type": "cancel_last_message"})
        res = ws.receive_json()
        assert res["type"] == "cancel_last_message_error"
        assert "already ended" in res["detail"]


def test_end_session_returns_session_ended(ws_env: SimpleNamespace) -> None:
    with TestClient(ws_env.app) as client, client.websocket_connect("/ws/chat") as ws:
        _authenticate(ws)
        _start_learning(ws)

        ws.send_json({"type": "end_session"})
        assert ws.receive_json()["type"] == "session_ended"


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

    async def fake_get_pool() -> asyncpg.Pool:
        return test_pool

    monkeypatch.setattr(chat, "get_pool", fake_get_pool)
    monkeypatch.setattr(ws_auth, "verify_jwt", lambda token: {"sub": user_id})

    graph = FakeGraph()
    inbound = [
        json.dumps({"type": "authenticate", "token": "x"}),
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
    assert human.additional_kwargs["intake_answers"] == {"purpose": "", "source": ["書籍"], "prior_knowledge": ""}


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

    assert res == {"type": "cancel_last_message_error", "detail": "Intake answers cannot be edited"}


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

    assert res == {"type": "cancel_last_message_error", "detail": "Intake answers cannot be edited"}


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
