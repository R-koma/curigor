from collections.abc import Mapping, Sequence
from typing import Any

from graph.output_schemas import MapDialogueTurnAnalysis, MapUserIntent
from graph.state import DepthMapState, MapAspectProgress, PhaseStepRecord

MAX_QUESTIONS = 3
PHASE_STATE_KEYS = ("dialogue_phase", "question_queue", "question_index", "asked_aspect_ids", "question_hinted")
START_QUESTIONS_KEY = "start_questions"
FLOW_GUIDE = "話したい順に説明してください。話し終えたら、気になった点をいくつか聞きます。"

_REACHED_STAGES = ("reasoned", "applied")


def reached_ids(map_covered: Sequence[MapAspectProgress]) -> set[str]:
    return {c["aspect_id"] for c in map_covered if c["reached_stage"] in _REACHED_STAGES}


def queued_aspect_id(queue: Sequence[str] | None, index: int | None) -> str:
    if not queue or index is None or index >= len(queue):
        return ""
    return queue[index]


def pending_question_ids(
    depth_map: DepthMapState, map_covered: Sequence[MapAspectProgress], asked: Sequence[str]
) -> list[str]:
    reached = reached_ids(map_covered)
    excluded = reached | set(asked)
    candidates = [a["id"] for a in depth_map["aspects"] if a["is_core"] and a["id"] not in excluded]
    return candidates[:MAX_QUESTIONS]


def pending_question_count(values: Mapping[str, Any]) -> int | None:
    if values.get("dialogue_phase") != "free":
        return None
    depth_map = values.get("depth_map")
    if not depth_map:
        return None
    map_covered = values.get("map_covered") or []
    if not map_covered:
        return None
    return len(pending_question_ids(depth_map, map_covered, values.get("asked_aspect_ids") or []))


def start_requested(values: Mapping[str, Any]) -> bool:
    if values.get("dialogue_phase") != "free":
        return False
    messages = values.get("messages") or []
    last = messages[-1] if messages else None
    return last is not None and last.type == "human" and bool(last.additional_kwargs.get(START_QUESTIONS_KEY))


def _previous_step(values: Mapping[str, Any]) -> PhaseStepRecord | None:
    previous = values.get("turn_analysis")
    return previous.get("phase_step") if previous else None


def _free_step(
    values: Mapping[str, Any],
    analysis: MapDialogueTurnAnalysis | None,
    depth_map: DepthMapState,
    map_covered: Sequence[MapAspectProgress],
    start: bool,
    fallback_intent: MapUserIntent,
) -> PhaseStepRecord:
    asked = list(values.get("asked_aspect_ids") or [])
    step = PhaseStepRecord(
        kind=None,
        phase="free",
        queue=[],
        index=None,
        asked=asked,
        total=0,
        shortened=False,
        offer_end=False,
        unknown_streak=0,
        start_requested=start,
        hinted=False,
    )
    intent = analysis.user_intent if analysis is not None else fallback_intent
    if start or intent == "exhausted":
        queue = pending_question_ids(depth_map, map_covered, asked)
        if not queue:
            return {**step, "kind": "finish", "offer_end": True}
        return {
            **step,
            "kind": "ask",
            "phase": "questions",
            "queue": queue,
            "index": 0,
            "asked": [*asked, queue[0]],
            "total": len(queue),
        }
    if intent in ("end_session", "dont_know"):
        return step
    if analysis is not None and analysis.has_misconception:
        return {**step, "kind": "correct"}
    if intent == "explanation":
        return {**step, "kind": "listen"}
    if intent == "question":
        return {**step, "kind": "answer"}
    return step


def _questions_step(
    values: Mapping[str, Any],
    analysis: MapDialogueTurnAnalysis | None,
    map_covered: Sequence[MapAspectProgress],
    fallback_intent: MapUserIntent,
) -> PhaseStepRecord:
    queue = list(values.get("question_queue") or [])
    index = values.get("question_index") or 0
    asked = list(values.get("asked_aspect_ids") or [])
    previous = _previous_step(values)
    total = previous["total"] if previous is not None and previous["phase"] == "questions" else len(queue)
    step = PhaseStepRecord(
        kind=None,
        phase="questions",
        queue=queue,
        index=index,
        asked=asked,
        total=total,
        shortened=False,
        offer_end=False,
        unknown_streak=0,
        start_requested=False,
        hinted=bool(values.get("question_hinted")),
    )
    intent = analysis.user_intent if analysis is not None else fallback_intent
    misconception = analysis is not None and analysis.has_misconception
    if intent == "end_session":
        return step
    if intent == "question" and not misconception:
        return {**step, "kind": "reask"}
    unknown_streak = 0
    if intent in ("dont_know", "partial_dont_know") and not misconception:
        if not step.get("hinted"):
            return {**step, "kind": "hint", "unknown_streak": 1, "hinted": True}
        unknown_streak = 2

    step = {**step, "hinted": False}
    reached = reached_ids(map_covered)
    later = queue[index + 1 :]
    remaining = [aspect_id for aspect_id in later if aspect_id not in reached]
    shortened = len(remaining) < len(later)
    if not remaining:
        return {
            **step,
            "kind": "finish",
            "phase": "free",
            "queue": [],
            "index": None,
            "shortened": shortened,
            "offer_end": True,
            "unknown_streak": unknown_streak,
        }
    return {
        **step,
        "kind": "ask",
        "queue": [*queue[: index + 1], *remaining],
        "index": index + 1,
        "asked": [*asked, remaining[0]],
        "shortened": shortened,
        "unknown_streak": unknown_streak,
    }


def plan_phase_step(
    values: Mapping[str, Any],
    analysis: MapDialogueTurnAnalysis | None,
    depth_map: DepthMapState,
    map_covered: Sequence[MapAspectProgress],
    *,
    start: bool,
    fallback_intent: MapUserIntent = "explanation",
) -> PhaseStepRecord | None:
    phase = values.get("dialogue_phase")
    if phase is None:
        return None
    if phase == "questions" and values.get("question_queue"):
        return _questions_step(values, analysis, map_covered, fallback_intent)
    return _free_step(values, analysis, depth_map, map_covered, start, fallback_intent)
