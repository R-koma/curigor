from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from graph.llm import llm
from graph.prompts import REVIEW_SYSTEM_PROMPT, build_focus_section
from graph.state import LearningState


async def review_start(state: LearningState) -> dict[str, Any]:
    """復習フローの開始：既存ノートを文脈に注入した LLM の初期応答"""
    prompt = REVIEW_SYSTEM_PROMPT.format(
        topic=state["topic"],
        content=state["note_content"],
        summary=state["note_summary"],
        focus_section=build_focus_section(state.get("prior_improvements"), state.get("review_focus_aspects")),
        intent_section="",
    )

    user_message = HumanMessage(content=state["topic"])
    response = await llm.ainvoke([SystemMessage(content=prompt), user_message])

    return {
        "messages": [user_message, response],
        "turn_count": 1,
        "should_generate_note": False,
    }
