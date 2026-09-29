"""地図駆動の学習対話（聞き取り完了後）。learning_dialogue.py の legacy TurnPlan/prepare_turn/respond と対になる。"""

from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from graph.depth_map import depth_map_progress, merge_map_coverage
from graph.llm import llm
from graph.multimodal import load_image_blocks
from graph.nodes._map_turn_analysis import analyze_map_dialogue_turn
from graph.nodes._shared import recent_messages_block
from graph.output_schemas import MapDialogueTurnAnalysis
from graph.prompts import format_learning_plan_fields
from graph.prompts.map_question import build_map_question_prompt
from graph.prompts.question import classify_user_intent
from graph.state import DepthMapState, LearningState, MapAspectProgress, TurnAnalysisRecord
from storage import get_storage


@dataclass(frozen=True)
class MapTurnPlan:
    """事前分析が決めた、このターンのプロンプトへ注入する値。"""

    depth_map: DepthMapState
    map_covered: list[MapAspectProgress] = field(default_factory=list)
    analysis: MapDialogueTurnAnalysis | None = None
    wrap_up: bool = False


def _to_record(plan: MapTurnPlan) -> TurnAnalysisRecord | None:
    if plan.analysis is None:
        return None
    aspect = next((a for a in plan.depth_map["aspects"] if a["id"] == plan.analysis.selected_aspect_id), None)
    label = aspect["name"] if aspect else plan.analysis.selected_aspect_id
    return TurnAnalysisRecord(
        response_mode=plan.analysis.response_mode,
        selected_aspect=label,
        selected_aspect_id=plan.analysis.selected_aspect_id,
        has_misconception=plan.analysis.has_misconception,
        error_summary=plan.analysis.error_summary,
        wrap_up=plan.wrap_up,
    )


def _turn_context(state: LearningState) -> tuple[str, dict[str, str]]:
    recent_messages = recent_messages_block(state)
    plan_fields = format_learning_plan_fields(
        learning_goal=state.get("learning_goal"),
        focus_aspects=state.get("focus_aspects"),
    )
    return recent_messages, plan_fields


async def prepare_map_turn(state: LearningState) -> MapTurnPlan:
    depth_map = state["depth_map"]
    map_covered: list[MapAspectProgress] = list(state.get("map_covered") or [])
    recent_messages, plan_fields = _turn_context(state)
    analysis: MapDialogueTurnAnalysis | None = None
    if classify_user_intent(state["messages"]) == "dialogue":
        analysis = await analyze_map_dialogue_turn(
            state,
            recent_messages=recent_messages,
            plan_fields=plan_fields,
            depth_map=depth_map,
            map_covered=map_covered,
        )
        if analysis is not None:
            map_covered, depth_map = merge_map_coverage(map_covered, analysis.observations, depth_map)
    wrap_up = (
        analysis is not None
        and not analysis.has_misconception
        and not state.get("wrap_up_offered")
        and depth_map_progress(map_covered, depth_map).is_complete
    )
    return MapTurnPlan(depth_map=depth_map, map_covered=map_covered, analysis=analysis, wrap_up=wrap_up)


async def respond_map(state: LearningState, plan: MapTurnPlan) -> dict[str, Any]:
    recent_messages, plan_fields = _turn_context(state)
    question_prompt, intent = build_map_question_prompt(
        topic=state["topic"],
        recent_messages=recent_messages,
        plan_fields=plan_fields,
        messages=state["messages"],
        depth_map=plan.depth_map,
        map_covered=plan.map_covered,
        turn_analysis=plan.analysis,
        wrap_up=plan.wrap_up,
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
                "intent": intent,
                "response_mode": plan.analysis.response_mode if plan.analysis else None,
                "selected_aspect_id": plan.analysis.selected_aspect_id if plan.analysis else None,
                "wrap_up": plan.wrap_up,
            }
        },
    )

    return {
        "messages": [response],
        "turn_count": state["turn_count"] + 1,
        "should_generate_note": False,
        "depth_map": plan.depth_map,
        "map_covered": plan.map_covered,
        "turn_analysis": _to_record(plan),
        "wrap_up_offered": bool(state.get("wrap_up_offered")) or plan.wrap_up,
    }
