"""地図駆動の学習対話の応答生成プロンプト。question.py のモード構造を再利用する。"""

from collections.abc import Sequence
from typing import Any

from graph.depth_map import format_map_coverage, next_stage, question_for
from graph.output_schemas import MapDialogueTurnAnalysis
from graph.prompts.question import (
    MODE_DIALOGUE,
    MODE_HINT,
    MODE_UNKNOWN_A,
    MODE_UNKNOWN_B,
    MODE_UNKNOWN_C,
    MODE_WRAP_UP,
    QUESTION_PROMPT_BASE,
    UserIntent,
    build_mode_section,
    classify_user_intent,
)
from graph.state import DepthMapState, MapAspectProgress, MapStage

_MODE_SECTIONS: dict[UserIntent, str] = {
    "exhausted": MODE_HINT,
    "unknown_a": MODE_UNKNOWN_A,
    "unknown_b": MODE_UNKNOWN_B,
    "unknown_c": MODE_UNKNOWN_C,
}


def _reached_stage(aspect_id: str, map_covered: Sequence[MapAspectProgress]) -> MapStage | None:
    for c in map_covered:
        if c["aspect_id"] == aspect_id:
            return c["reached_stage"]
    return None


def _build_map_dialogue_section(
    analysis: MapDialogueTurnAnalysis, depth_map: DepthMapState, map_covered: Sequence[MapAspectProgress]
) -> str:
    aspect = next((a for a in depth_map["aspects"] if a["id"] == analysis.selected_aspect_id), None)
    if aspect is None:
        return build_mode_section(
            response_mode=analysis.response_mode,
            selected_aspect_label=analysis.selected_aspect_id,
            error_summary=analysis.error_summary,
        )
    # Check if this turn's analysis has observations for this aspect
    current_obs = next((o for o in analysis.observations if o.aspect_id == analysis.selected_aspect_id), None)
    if current_obs:
        current_stage: MapStage | None = current_obs.reached_stage
    else:
        current_stage = _reached_stage(aspect["id"], map_covered)
    target_stage = next_stage(current_stage)
    hint = (
        "### この観点の核心（地図より）\n"
        f"{question_for(aspect, target_stage)}\n"
        "この核心に向かって問いを組み立てる。日常的な具体例だけで終わらせない。"
    )
    return build_mode_section(
        response_mode=analysis.response_mode,
        selected_aspect_label=aspect["name"],
        error_summary=analysis.error_summary,
        extra_hint=hint,
    )


def _build_coverage_section(map_covered: Sequence[MapAspectProgress], depth_map: DepthMapState) -> str:
    lines = format_map_coverage(map_covered, depth_map)
    if not lines:
        return ""
    return (
        "## カバー済み観点と到達度（過去ターン累積）\n"
        f"{lines}\n"
        "上記の観点は記載の段階まで説明済みとして扱い、同じ深さの質問を繰り返さない。\n\n"
    )


def build_map_question_prompt(
    *,
    topic: str,
    recent_messages: str,
    plan_fields: dict[str, str],
    messages: Sequence[Any],
    depth_map: DepthMapState,
    map_covered: Sequence[MapAspectProgress],
    turn_analysis: MapDialogueTurnAnalysis | None,
    wrap_up: bool = False,
) -> tuple[str, UserIntent]:
    intent = classify_user_intent(messages)
    if intent == "dialogue" and wrap_up:
        mode_section = MODE_WRAP_UP
    elif intent == "dialogue" and turn_analysis is not None:
        mode_section = _build_map_dialogue_section(turn_analysis, depth_map, map_covered)
    elif intent == "dialogue":
        mode_section = MODE_DIALOGUE
    else:
        mode_section = _MODE_SECTIONS[intent]
    template = QUESTION_PROMPT_BASE + "\n" + mode_section
    prompt = template.format(
        topic=topic,
        recent_messages=recent_messages,
        coverage_section=_build_coverage_section(map_covered, depth_map),
        **plan_fields,
    )
    return prompt, intent
