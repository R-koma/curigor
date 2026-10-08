import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Self
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from evals.dataset import SourceTrace, trace_route
from evals.retry import QuotaExhausted, is_quota_exhausted, is_transient
from evals.tools.capture import CAPTURED_BY, MAP_ROUTE
from graph.nodes._map_dialogue import MapTurnPlan, respond_map
from graph.nodes.learning_dialogue import TurnPlan, learning_dialogue, respond
from graph.output_schemas import DialogueTurnAnalysis, MapDialogueTurnAnalysis
from graph.state import LearningState

logger = logging.getLogger(__name__)

_GENERATE_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 1.0
_EVAL_USER_ID = "eval-regression"


@dataclass(frozen=True)
class Generation:
    output: str
    turn_analysis: dict[str, Any] | None
    covered_aspects: list[dict[str, Any]]
    turn_count: int
    map_covered: list[dict[str, Any]] = field(default_factory=list)
    depth_map: dict[str, Any] | None = None

    @classmethod
    def from_checkpoint(cls, cached: dict[str, Any]) -> Self:
        return cls(
            output=cached["output"],
            turn_analysis=cached["turn_analysis"],
            covered_aspects=cached["covered_aspects"],
            turn_count=cached["turn_count"],
            map_covered=cached.get("map_covered") or [],
            depth_map=cached.get("depth_map"),
        )

    def turn_decision(self) -> dict[str, Any] | None:
        """そのターンがプロンプトへ注入した決定値（capture の `turn_decision` と同じ形）。"""
        if not self.turn_analysis:
            return None
        if self.depth_map is not None:
            return {**self.turn_analysis, "depth_map": self.depth_map, "map_covered": self.map_covered}
        return {**self.turn_analysis, "covered_aspects": self.covered_aspects}


def replay_blocker(trace: SourceTrace, replay_mode: str = "full") -> str | None:
    """本番のターンを忠実に再現できない理由。再現できるなら None。

    手で書いたレコードは `conversation_history` が本番の `messages` と 1:1 になっておらず
    （トピック発話や learning_start の応答が欠けている）、`classify_user_intent` の判定と
    プロンプトの直近履歴が本番と変わる。capture 由来だけが 1:1 を保証できる。
    """
    if trace.meta.get("captured_by") != CAPTURED_BY:
        return "capture 由来でないため conversation_history が本番の state と 1:1 でない"
    if replay_mode == "pinned" and not trace.has_turn_decision:
        return "turn_decision を持たないため、そのターンの決定を注入できない"
    if replay_mode == "full" and (trace.turn_decision or {}).get("topic_correction"):
        return "トピック訂正への回答とヘッダーでの編集のターンは、印が conversation_history に無く再現できない"
    return None


def to_turn_plan(trace: SourceTrace) -> TurnPlan:
    """保存済みの決定内容から、そのターンがプロンプトへ注入した値を組み直す。

    `observations` は `covered_aspects` にマージ済みなので保存しておらず、ここでは空で足りる
    （プロンプトが読むのは response_mode / selected_aspect / error_summary だけ）。
    """
    decision = trace.turn_decision
    if decision is None:
        graph_state = trace.input["graph_state"]
        return TurnPlan(covered_aspects=list(graph_state.get("covered_aspects") or []))
    return TurnPlan(
        covered_aspects=list(decision.get("covered_aspects") or []),
        analysis=DialogueTurnAnalysis(
            observations=[],
            response_mode=decision["response_mode"],
            selected_aspect=decision["selected_aspect"],
            # 改訂前に capture したレコードはこのキーを持たない（そのターンは誤り未検出として再生する）
            has_misconception=decision.get("has_misconception", False),
            error_summary=decision["error_summary"],
        ),
        wrap_up=bool(decision.get("wrap_up", False)),
    )


def to_map_turn_plan(trace: SourceTrace) -> MapTurnPlan:
    decision = trace.turn_decision
    if decision is None:
        graph_state = trace.input["graph_state"]
        return MapTurnPlan(
            depth_map=graph_state["depth_map"],
            map_covered=list(graph_state.get("map_covered") or []),
        )
    return MapTurnPlan(
        depth_map=decision["depth_map"],
        map_covered=list(decision["map_covered"]),
        analysis=MapDialogueTurnAnalysis(
            user_intent=decision.get("user_intent", "explanation"),
            observations=[],
            has_misconception=decision["has_misconception"],
            error_summary=decision["error_summary"],
            response_mode=decision["response_mode"],
            selected_aspect_id=decision["selected_aspect_id"],
        ),
        wrap_up=bool(decision["wrap_up"]),
        topic_correction=decision.get("topic_correction"),
        unknown_streak=decision.get("unknown_streak", 0),
    )


def to_state(trace: SourceTrace) -> LearningState:
    graph_state = trace.input["graph_state"]
    messages: list[BaseMessage] = [
        AIMessage(content=m["content"]) if m["role"] == "assistant" else HumanMessage(content=m["content"])
        for m in trace.input["conversation_history"]
    ]
    state: LearningState = {
        "user_id": _EVAL_USER_ID,
        "dialogue_session_id": uuid4(),
        "note_id": uuid4(),
        "messages": messages,
        "topic": graph_state["topic"],
        "turn_count": graph_state.get("turn_count") or trace.turn,
        "should_generate_note": False,
        "session_type": "learning",
    }
    if graph_state.get("learning_goal"):
        state["learning_goal"] = graph_state["learning_goal"]
    if graph_state.get("focus_aspects"):
        state["focus_aspects"] = graph_state["focus_aspects"]
    if graph_state.get("covered_aspects"):
        state["covered_aspects"] = graph_state["covered_aspects"]
    state["wrap_up_offered"] = bool(graph_state.get("wrap_up_offered", True))
    if trace_route(trace) == MAP_ROUTE:
        _add_map_state(state, graph_state)
    return state


def _add_map_state(state: LearningState, graph_state: dict[str, Any]) -> None:
    state["intake_complete"] = True
    state["depth_map"] = graph_state["depth_map"]
    state["map_covered"] = list(graph_state.get("map_covered") or [])
    state["intake_message_count"] = graph_state["intake_message_count"]
    state["wrap_up_offered"] = bool(graph_state["wrap_up_offered"])
    if graph_state.get("learning_source"):
        state["learning_source"] = graph_state["learning_source"]
    if graph_state.get("prior_knowledge"):
        state["prior_knowledge"] = graph_state["prior_knowledge"]
    if graph_state.get("related_notes"):
        state["related_notes"] = graph_state["related_notes"]


def message_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            parts.append(str(block.get("text", "")))
    return "".join(parts)


async def _generate_output_once(trace: SourceTrace, replay_mode: str) -> Generation:
    state = to_state(trace)
    if replay_mode != "pinned":
        result = await learning_dialogue(state)
    elif trace_route(trace) == MAP_ROUTE:
        result = await respond_map(state, to_map_turn_plan(trace))
    else:
        result = await respond(state, to_turn_plan(trace))
    return Generation(
        output=message_text(result["messages"][0]),
        turn_analysis=result.get("turn_analysis"),
        covered_aspects=list(result.get("covered_aspects") or []),
        turn_count=result["turn_count"],
        map_covered=list(result.get("map_covered") or []),
        depth_map=result.get("depth_map"),
    )


async def generate_output(trace: SourceTrace, replay_mode: str = "full") -> Generation:
    """本番の対話ノードを呼んで応答を作り直す（regression モード）。

    `full` は事前分析込みで実行するのでプロンプト改訂の効果と分析の揺れが両方入る。
    `pinned` は保存済みの決定（`turn_decision`）を注入して応答生成だけを再実行するので、
    分析の揺れを除いた「プロンプトを直した効果」だけが見える。

    接続断・タイムアウト・レート制限・5xx はバックオフして最大 `_GENERATE_MAX_ATTEMPTS` 回まで
    再試行する（生成は同じ入力を投げ直すだけで冪等）。課金枯渇は再試行しても直らないので
    `QuotaExhausted` を送出し、呼び出し元（`run`）で実行全体を止める。
    """
    last_error: Exception | None = None
    for attempt in range(1, _GENERATE_MAX_ATTEMPTS + 1):
        try:
            return await _generate_output_once(trace, replay_mode)
        except Exception as exc:
            if is_quota_exhausted(exc):
                raise QuotaExhausted(str(exc)) from exc
            if not is_transient(exc) or attempt == _GENERATE_MAX_ATTEMPTS:
                raise
            last_error = exc
            logger.warning("generate_output attempt %d/%d raised: %s", attempt, _GENERATE_MAX_ATTEMPTS, exc)
            await asyncio.sleep(_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
    assert last_error is not None  # ループは return か raise で必ず抜ける
    raise last_error
