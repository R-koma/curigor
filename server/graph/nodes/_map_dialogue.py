"""地図駆動の学習対話（聞き取り完了後）。learning_dialogue.py の legacy TurnPlan/prepare_turn/respond と対になる。"""

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from graph.depth_map import depth_map_progress, merge_map_coverage, resolve_aspect
from graph.intake_card import MAX_TOPIC_LENGTH
from graph.llm import llm
from graph.multimodal import load_image_blocks
from graph.nodes._depth_map_generation import generate_depth_map
from graph.nodes._map_turn_analysis import analyze_map_dialogue_turn
from graph.nodes._shared import recent_messages_block
from graph.output_schemas import MapDialogueTurnAnalysis
from graph.prompts import format_learning_plan_fields
from graph.prompts.map_question import MAP_PROMPT_FINGERPRINT, build_map_question_prompt
from graph.prompts.question import trailing_unknown_count
from graph.session_end import end_confirmation_after
from graph.state import (
    DepthMapState,
    EndConfirmationStatus,
    LearningState,
    MapAspectProgress,
    PendingTopicCorrection,
    TopicCorrectionRecord,
    TopicCorrectionStatus,
    TurnAnalysisRecord,
)
from graph.topic_correction import topic_correction_card, topic_correction_text
from storage import get_storage


@dataclass(frozen=True)
class MapTurnPlan:
    """事前分析が決めた、このターンのプロンプトへ注入する値。"""

    depth_map: DepthMapState
    map_covered: list[MapAspectProgress] = field(default_factory=list)
    analysis: MapDialogueTurnAnalysis | None = None
    wrap_up: bool = False
    topic_correction: TopicCorrectionRecord | None = None
    unknown_streak: int = 0
    end_confirmation: EndConfirmationStatus | None = None


def _asked_record(correction: TopicCorrectionRecord) -> TurnAnalysisRecord:
    return TurnAnalysisRecord(
        response_mode="expand",
        selected_aspect="",
        selected_aspect_id="",
        has_misconception=False,
        error_summary="",
        wrap_up=False,
        topic_correction=correction,
    )


def _to_record(plan: MapTurnPlan) -> TurnAnalysisRecord | None:
    if plan.analysis is None:
        if plan.topic_correction is not None and plan.topic_correction["status"] == "asked":
            return _asked_record(plan.topic_correction)
        return None
    aspect = next((a for a in plan.depth_map["aspects"] if a["id"] == plan.analysis.selected_aspect_id), None)
    label = aspect["name"] if aspect else plan.analysis.selected_aspect_id
    record = TurnAnalysisRecord(
        response_mode=plan.analysis.response_mode,
        selected_aspect=label,
        selected_aspect_id=plan.analysis.selected_aspect_id,
        has_misconception=plan.analysis.has_misconception,
        error_summary=plan.analysis.error_summary,
        wrap_up=plan.wrap_up,
    )
    if plan.analysis.user_intent != "explanation":
        record["user_intent"] = plan.analysis.user_intent
    if plan.unknown_streak:
        record["unknown_streak"] = plan.unknown_streak
    if plan.topic_correction is not None:
        record["topic_correction"] = plan.topic_correction
    return record


def _turn_context(state: LearningState) -> tuple[str, dict[str, str]]:
    recent_messages = recent_messages_block(state)
    plan_fields = format_learning_plan_fields(
        learning_goal=state.get("learning_goal"),
        focus_aspects=state.get("focus_aspects"),
    )
    return recent_messages, plan_fields


def _dialogue_messages(state: LearningState) -> list[BaseMessage]:
    return list(state["messages"][state.get("intake_message_count", 0) :])


def _normalized_topic(topic: str) -> str:
    return unicodedata.normalize("NFKC", topic).strip().lower()


def _requested_topic(state: LearningState, analysis: MapDialogueTurnAnalysis) -> str:
    candidate = analysis.corrected_topic.strip()[:MAX_TOPIC_LENGTH]
    if not candidate or _normalized_topic(candidate) == _normalized_topic(state["topic"]):
        return ""
    return candidate


def _topic_correction_answer(state: LearningState) -> Literal["accept", "decline"] | None:
    last = state["messages"][-1] if state["messages"] else None
    if last is None or last.type != "human":
        return None
    answer = last.additional_kwargs.get("topic_correction_answer")
    return answer if answer in ("accept", "decline") else None


def _focus_analysis(depth_map: DepthMapState, map_covered: list[MapAspectProgress]) -> MapDialogueTurnAnalysis:
    reached = {c["aspect_id"] for c in map_covered if c["reached_stage"] in ("reasoned", "applied")}
    core = [a for a in depth_map["aspects"] if a["is_core"]]
    target = next((a for a in core if a["id"] not in reached), None) or (core or depth_map["aspects"])[0]
    return MapDialogueTurnAnalysis(
        observations=[], has_misconception=False, response_mode="expand", selected_aspect_id=target["id"]
    )


def _unknown_streak(state: LearningState, analysis: MapDialogueTurnAnalysis | None) -> int:
    if analysis is None or analysis.user_intent != "dont_know":
        return 0
    previous = state.get("turn_analysis")
    if previous is None:
        # 意図の判定を入れる前の地図の経路は「わからない」のターンで事前分析を飛ばし、turn_analysis を空にしていた
        return trailing_unknown_count(state["messages"][:-1]) + 1
    if previous.get("user_intent") != "dont_know":
        return 1
    return previous.get("unknown_streak", 1) + 1


def _correction_plan(
    state: LearningState, new_topic: str, status: TopicCorrectionStatus, new_map: DepthMapState | None = None
) -> MapTurnPlan:
    depth_map = new_map or state["depth_map"]
    map_covered: list[MapAspectProgress] = [] if new_map else list(state.get("map_covered") or [])
    return MapTurnPlan(
        depth_map=depth_map,
        map_covered=map_covered,
        analysis=None if status == "asked" else _focus_analysis(depth_map, map_covered),
        topic_correction=TopicCorrectionRecord(previous_topic=state["topic"], new_topic=new_topic, status=status),
    )


async def _answer_topic_correction(
    state: LearningState, pending: PendingTopicCorrection, answer: Literal["accept", "decline"]
) -> MapTurnPlan:
    new_topic = pending["new_topic"]
    if answer == "decline":
        return _correction_plan(state, new_topic, "declined")
    new_map = await generate_depth_map(
        topic=new_topic,
        purpose=state.get("learning_goal") or "",
        source=state.get("learning_source") or "",
        prior_knowledge=state.get("prior_knowledge") or "",
        related_notes=state.get("related_notes") or [],
    )
    if new_map is None:
        return _correction_plan(state, new_topic, "failed")
    return _correction_plan(state, new_topic, "accepted", new_map)


async def prepare_map_turn(state: LearningState) -> MapTurnPlan:
    pending = state.get("pending_topic_correction")
    answer = _topic_correction_answer(state)
    if pending and answer:
        return await _answer_topic_correction(state, pending, answer)
    depth_map = state["depth_map"]
    map_covered: list[MapAspectProgress] = list(state.get("map_covered") or [])
    recent_messages, plan_fields = _turn_context(state)
    analysis = await analyze_map_dialogue_turn(
        state,
        recent_messages=recent_messages,
        plan_fields=plan_fields,
        depth_map=depth_map,
        map_covered=map_covered,
    )
    new_topic = _requested_topic(state, analysis) if analysis is not None else ""
    if new_topic:
        return _correction_plan(state, new_topic, "asked")
    if analysis is not None:
        map_covered, depth_map = merge_map_coverage(map_covered, analysis.observations, depth_map)
        if analysis.selected_aspect_id.strip():
            selected_id, depth_map = resolve_aspect(analysis.selected_aspect_id, depth_map)
            analysis = analysis.model_copy(update={"selected_aspect_id": selected_id})
    wrap_up = (
        analysis is not None
        and analysis.user_intent == "explanation"
        and not analysis.has_misconception
        and not state.get("wrap_up_offered")
        and depth_map_progress(map_covered, depth_map).is_complete
    )
    return MapTurnPlan(
        depth_map=depth_map,
        map_covered=map_covered,
        analysis=analysis,
        wrap_up=wrap_up,
        unknown_streak=_unknown_streak(state, analysis),
        end_confirmation=end_confirmation_after(
            state.get("end_confirmation"),
            wants_to_end=analysis is not None and analysis.user_intent == "end_session",
            offer=wrap_up,
        ),
    )


async def respond_map(state: LearningState, plan: MapTurnPlan) -> dict[str, Any]:
    correction = plan.topic_correction
    if correction is not None and correction["status"] == "asked":
        return {
            "messages": [
                AIMessage(
                    content=topic_correction_text(correction["previous_topic"], correction["new_topic"]),
                    additional_kwargs={
                        "topic_correction_card": topic_correction_card(
                            correction["previous_topic"], correction["new_topic"]
                        )
                    },
                )
            ],
            "turn_count": state["turn_count"] + 1,
            "should_generate_note": False,
            "depth_map": plan.depth_map,
            "map_covered": plan.map_covered,
            "turn_analysis": _to_record(plan),
            "wrap_up_offered": bool(state.get("wrap_up_offered")),
            "pending_topic_correction": {"new_topic": correction["new_topic"]},
            "end_confirmation": None,
        }
    if plan.end_confirmation == "confirmed":
        return {
            "turn_count": state["turn_count"] + 1,
            "should_generate_note": False,
            "depth_map": plan.depth_map,
            "map_covered": plan.map_covered,
            "turn_analysis": _to_record(plan),
            "wrap_up_offered": bool(state.get("wrap_up_offered")),
            "pending_topic_correction": None,
            "end_confirmation": "confirmed",
        }
    accepted = correction is not None and correction["status"] == "accepted"
    topic = correction["new_topic"] if correction is not None and accepted else state["topic"]
    recent_messages, plan_fields = _turn_context(state)
    question_prompt, intent = build_map_question_prompt(
        topic=topic,
        recent_messages=recent_messages,
        plan_fields=plan_fields,
        messages=_dialogue_messages(state),
        depth_map=plan.depth_map,
        map_covered=plan.map_covered,
        turn_analysis=plan.analysis,
        wrap_up=plan.wrap_up,
        topic_correction=correction,
        unknown_streak=plan.unknown_streak,
        related_notes=state.get("related_notes") or [],
    )
    llm_messages: list[BaseMessage] = [SystemMessage(content=question_prompt)]
    if state["messages"]:
        image_blocks = await load_image_blocks(state["messages"][-1], get_storage())
        if image_blocks:
            llm_messages.append(HumanMessage(content=image_blocks))

    response = await llm.ainvoke(
        llm_messages,
        config={
            "metadata": {
                "prompt_fingerprint": MAP_PROMPT_FINGERPRINT,
                "intent": intent,
                "response_mode": plan.analysis.response_mode if plan.analysis else None,
                "selected_aspect_id": plan.analysis.selected_aspect_id if plan.analysis else None,
                "wrap_up": plan.wrap_up,
                "topic_correction": correction["status"] if correction else None,
                "unknown_streak": plan.unknown_streak,
            }
        },
    )

    updates: dict[str, Any] = {
        "messages": [response],
        "turn_count": state["turn_count"] + 1,
        "should_generate_note": False,
        "depth_map": plan.depth_map,
        "map_covered": plan.map_covered,
        "turn_analysis": _to_record(plan),
        "wrap_up_offered": False if accepted else bool(state.get("wrap_up_offered")) or plan.wrap_up,
        "pending_topic_correction": None,
        "end_confirmation": plan.end_confirmation,
    }
    if accepted:
        updates["topic"] = topic
    return updates
