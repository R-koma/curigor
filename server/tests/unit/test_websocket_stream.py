import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from api.websocket.chat import _stream_ai_response
from graph.llm import INTERNAL_LLM_TAG


class _FakeGraph:
    def __init__(
        self,
        events: list[tuple[Any, dict[str, Any]]],
        state_values: dict[str, Any] | None = None,
        *,
        aget_state_error: Exception | None = None,
    ) -> None:
        self._events = events
        self._state_values = state_values or {}
        self._aget_state_error = aget_state_error
        self.state_configs: list[Any] = []

    async def astream(self, input: Any, config: Any, stream_mode: str) -> Any:
        for event in self._events:
            yield event

    async def aget_state(self, config: Any) -> SimpleNamespace:
        self.state_configs.append(config)
        if self._aget_state_error is not None:
            raise self._aget_state_error
        return SimpleNamespace(values=self._state_values)


async def test_internal_llm_chunks_are_not_streamed_to_client() -> None:
    events: list[tuple[Any, dict[str, Any]]] = [
        (AIMessageChunk(content="表示する"), {"langgraph_node": "learning_dialogue", "tags": []}),
        (
            AIMessageChunk(content='{"response_mode": "expand"}'),
            {"langgraph_node": "learning_dialogue", "tags": [INTERNAL_LLM_TAG]},
        ),
        (AIMessageChunk(content="チャンク"), {"langgraph_node": "learning_dialogue"}),
    ]
    websocket = AsyncMock()

    turn = await _stream_ai_response(_FakeGraph(events), None, {}, websocket)

    assert turn.content == "表示するチャンク"
    sent = [json.loads(call.args[0]) for call in websocket.send_text.call_args_list]
    chunk_contents = [m["content"] for m in sent if m.get("type") == "assistant_message_chunk"]
    assert chunk_contents == ["表示する", "チャンク"]


async def test_non_streaming_nodes_are_filtered() -> None:
    events: list[tuple[Any, dict[str, Any]]] = [
        (AIMessageChunk(content="分析結果"), {"langgraph_node": "generate_feedback", "tags": []}),
    ]
    websocket = AsyncMock()

    turn = await _stream_ai_response(_FakeGraph(events), None, {}, websocket)

    assert turn.content == ""
    sent = [json.loads(call.args[0]) for call in websocket.send_text.call_args_list]
    assert [m["type"] for m in sent] == ["assistant_message_end"]


async def test_end_message_carries_progress_read_from_the_progress_config() -> None:
    graph = _FakeGraph(
        [],
        state_values={"covered_aspects": [{"aspect": "計算量", "reached_depth": "exemplified"}]},
    )
    websocket = AsyncMock()
    base_config = {"configurable": {"thread_id": "t"}}

    await _stream_ai_response(graph, None, {"callbacks": ["handler"]}, websocket, progress_config=base_config)

    assert graph.state_configs == [base_config]
    sent = [json.loads(call.args[0]) for call in websocket.send_text.call_args_list]
    assert sent[-1] == {
        "type": "assistant_message_end",
        "progress": {
            "reached_aspects": ["計算量"],
            "target_count": 3,
            "is_complete": False,
            "aspects": [],
            "intake": None,
        },
    }


async def test_end_message_has_no_progress_without_progress_config() -> None:
    graph = _FakeGraph([])
    websocket = AsyncMock()

    await _stream_ai_response(graph, None, {}, websocket)

    sent = [json.loads(call.args[0]) for call in websocket.send_text.call_args_list]
    assert sent[-1] == {"type": "assistant_message_end", "progress": None}
    assert graph.state_configs == []


async def test_progress_read_failure_does_not_fail_the_turn() -> None:
    """進捗の取得は表示専用の副次情報であり、失敗してもターンの成否に影響させない。

    ここで例外を伝播させると、既に応答済みのターンが呼び出し側の except で
    未回答ターンとして扱われ、DB とチェックポイントの状態が不整合になる。
    """
    graph = _FakeGraph([], aget_state_error=RuntimeError("boom"))
    websocket = AsyncMock()
    base_config = {"configurable": {"thread_id": "t"}}

    turn = await _stream_ai_response(graph, None, {}, websocket, progress_config=base_config)

    assert turn.content == ""
    assert turn.question is None
    sent = [json.loads(call.args[0]) for call in websocket.send_text.call_args_list]
    assert sent[-1] == {"type": "assistant_message_end", "progress": None}


_CARD = {
    "questions": [
        {"key": "source", "header": "教材", "question": "q", "options": [{"label": "書籍"}], "multi_select": True}
    ]
}


async def test_intake_card_is_sent_before_end_when_nothing_was_streamed() -> None:
    state = {
        "topic": "React Hooks",
        "messages": [
            HumanMessage(content="Reactのフック"),
            AIMessage(content="React Hooksを学ぶんですね。", additional_kwargs={"intake_card": _CARD}),
        ],
    }
    websocket = AsyncMock()

    turn = await _stream_ai_response(_FakeGraph([], state), None, {}, websocket, progress_config={})

    sent = [json.loads(call.args[0]) for call in websocket.send_text.call_args_list]
    assert [m["type"] for m in sent] == ["intake_question", "assistant_message_end"]
    assert sent[0]["topic"] == "React Hooks"
    assert sent[0]["card"]["questions"][0]["options"][0]["label"] == "書籍"
    assert turn.content == "React Hooksを学ぶんですね。"
    assert turn.question is not None
    assert turn.question.topic == "React Hooks"


async def test_intake_card_is_sent_even_when_something_streamed() -> None:
    events: list[tuple[Any, dict[str, Any]]] = [
        (AIMessageChunk(content="ストリームされた本文"), {"langgraph_node": "learning_start", "tags": []}),
    ]
    state = {
        "topic": "React Hooks",
        "messages": [
            HumanMessage(content="Reactのフック"),
            AIMessage(content="ストリームされた本文", additional_kwargs={"intake_card": _CARD}),
        ],
    }
    websocket = AsyncMock()

    turn = await _stream_ai_response(_FakeGraph(events, state), None, {}, websocket, progress_config={})

    sent = [json.loads(call.args[0]) for call in websocket.send_text.call_args_list]
    assert [m["type"] for m in sent] == ["assistant_message_chunk", "intake_question", "assistant_message_end"]
    assert turn.content == "ストリームされた本文"


async def test_streamed_turn_never_reads_intake_card() -> None:
    events: list[tuple[Any, dict[str, Any]]] = [
        (AIMessageChunk(content="応答"), {"langgraph_node": "learning_dialogue", "tags": []}),
    ]
    websocket = AsyncMock()

    await _stream_ai_response(_FakeGraph(events, {}), None, {}, websocket, progress_config={})

    sent = [json.loads(call.args[0]) for call in websocket.send_text.call_args_list]
    assert "intake_question" not in [m["type"] for m in sent]


async def test_end_message_carries_no_progress_while_the_intake_card_is_open() -> None:
    state = {
        "topic": "React Hooks",
        "intake_complete": False,
        "messages": [
            HumanMessage(content="Reactのフック"),
            AIMessage(content="React Hooksを学ぶんですね。", additional_kwargs={"intake_card": _CARD}),
        ],
    }
    websocket = AsyncMock()

    await _stream_ai_response(_FakeGraph([], state), None, {}, websocket, progress_config={})

    sent = [json.loads(call.args[0]) for call in websocket.send_text.call_args_list]
    assert sent[-1] == {"type": "assistant_message_end", "progress": None}
