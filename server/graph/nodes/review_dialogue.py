from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from graph.llm import llm
from graph.multimodal import load_image_blocks, text_block
from graph.nodes._review_turn_analysis import analyze_review_turn
from graph.prompts import REVIEW_END_SESSION_SECTION, REVIEW_SYSTEM_PROMPT, build_focus_section
from graph.session_end import end_confirmation_after, review_answered
from graph.state import LearningState
from storage import get_storage


async def review_dialogue(state: LearningState) -> dict[str, Any]:
    analysis = await analyze_review_turn(state)
    wants_to_end = analysis is not None and analysis.wants_to_end_session
    end_confirmation = end_confirmation_after(state.get("end_confirmation"), wants_to_end=wants_to_end, offer=False)
    updates: dict[str, Any] = {
        "turn_count": state["turn_count"] + 1,
        "should_generate_note": False,
        "end_confirmation": end_confirmation,
        "review_answered": review_answered(state) or not wants_to_end,
    }
    if end_confirmation == "confirmed":
        return updates

    prompt = REVIEW_SYSTEM_PROMPT.format(
        topic=state["topic"],
        content=state.get("note_content", ""),
        summary=state.get("note_summary", ""),
        focus_section=build_focus_section(state.get("prior_improvements"), state.get("review_focus_aspects")),
        intent_section=REVIEW_END_SESSION_SECTION if end_confirmation == "offered" else "",
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
