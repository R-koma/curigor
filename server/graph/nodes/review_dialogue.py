from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from graph.llm import llm
from graph.multimodal import load_image_blocks, text_block
from graph.nodes._review_turn_analysis import analyze_review_turn
from graph.output_schemas import ReviewTurnAnalysis
from graph.prompts import (
    REVIEW_END_SESSION_SECTION,
    REVIEW_SYSTEM_PROMPT,
    build_focus_section,
    build_review_turn_section,
)
from graph.review_progress import ReviewPointState, ReviewTurnInput, ReviewTurnPlan, plan_review_turn
from graph.session_end import end_confirmation_after, review_answered
from graph.state import LearningState
from storage import get_storage


def _plan_turn(
    state: LearningState, points: list[ReviewPointState], analysis: ReviewTurnAnalysis | None
) -> ReviewTurnPlan:
    current_id = state.get("review_current_point_id")
    wrap_up_offered = bool(state.get("wrap_up_offered"))
    declined_end_wish = state.get("end_confirmation") == "offered" and current_id is not None
    turn = (
        None
        if analysis is None or (declined_end_wish and not analysis.wants_to_end_session)
        else ReviewTurnInput(
            current_point_explained=analysis.current_point_explained,
            explained_point_ids=analysis.explained_point_ids,
        )
    )
    plan = plan_review_turn(points, current_id, turn, wrap_up_offered=wrap_up_offered)
    if analysis is None or not analysis.wants_to_end_session:
        return plan
    kept = plan.points
    if not analysis.current_point_explained:
        original = next((p for p in points if p["id"] == current_id), None)
        if original is not None:
            kept = [original if p["id"] == current_id else p for p in plan.points]
    return ReviewTurnPlan(
        points=kept,
        current_point_id=current_id,
        hint_point=None,
        explain_point=None,
        ask_point=None,
        wrap_up=False,
    )


async def review_dialogue(state: LearningState) -> dict[str, Any]:
    analysis = await analyze_review_turn(state)
    wants_to_end = analysis is not None and analysis.wants_to_end_session
    review_points = state.get("review_points")
    plan = _plan_turn(state, review_points, analysis) if review_points else None
    end_confirmation = end_confirmation_after(
        state.get("end_confirmation"), wants_to_end=wants_to_end, offer=plan is not None and plan.wrap_up
    )
    updates: dict[str, Any] = {
        "turn_count": state["turn_count"] + 1,
        "should_generate_note": False,
        "end_confirmation": end_confirmation,
        "review_answered": review_answered(state) or not wants_to_end,
    }
    if plan is not None:
        updates["review_points"] = plan.points
        updates["review_current_point_id"] = plan.current_point_id
        updates["wrap_up_offered"] = plan.wrap_up or bool(state.get("wrap_up_offered"))
    if end_confirmation == "confirmed":
        return updates

    if plan is not None:
        focus_section = "" if wants_to_end else build_review_turn_section(plan)
    else:
        focus_section = build_focus_section(state.get("prior_improvements"), state.get("review_priority_aspects"))
    prompt = REVIEW_SYSTEM_PROMPT.format(
        topic=state["topic"],
        content=state.get("note_content", ""),
        summary=state.get("note_summary", ""),
        focus_section=focus_section,
        intent_section=REVIEW_END_SESSION_SECTION if wants_to_end else "",
    )
    history: list[BaseMessage] = list(state["messages"])
    if history:
        image_blocks = await load_image_blocks(history[-1], get_storage())
        if image_blocks:
            last = history[-1]
            text = last.content if isinstance(last.content, str) else ""
            history[-1] = HumanMessage(content=[text_block(text), *image_blocks])

    messages = [SystemMessage(content=prompt), *history]
    response = await llm.ainvoke(messages, task="review-dialogue")

    updates["messages"] = [response]
    return updates
