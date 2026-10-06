from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from graph.llm import llm
from graph.multimodal import load_image_blocks, text_block
from graph.prompts import REVIEW_SYSTEM_PROMPT, build_focus_section
from graph.state import LearningState
from storage import get_storage

# REVIEW_SYSTEM_PROMPT が「対話を終える」と判断したときに LLM が出力する
# リテラル。値はプロンプト本文（graph/prompts/review.py）の指示と一致させる。
REVIEW_END_SIGNAL = "LEARNING_END"


async def review_dialogue(state: LearningState) -> dict[str, Any]:
    """復習対話の継続。LLM が REVIEW_END_SIGNAL を返したら復習更新へ進む。

    学習セッションと異なり、終了判定は LLM が主体的に行う（自走終了）。
    """
    prompt = REVIEW_SYSTEM_PROMPT.format(
        topic=state["topic"],
        content=state.get("note_content", ""),
        summary=state.get("note_summary", ""),
        focus_section=build_focus_section(state.get("prior_improvements"), state.get("review_focus_aspects")),
    )
    history: list[BaseMessage] = list(state["messages"])
    if history:
        image_blocks = await load_image_blocks(history[-1], get_storage())
        if image_blocks:
            last = history[-1]
            text = last.content if isinstance(last.content, str) else ""
            history[-1] = HumanMessage(content=[text_block(text), *image_blocks])

    messages = [SystemMessage(content=prompt), *history]
    response = await llm.ainvoke(messages)

    content = response.content
    should_generate_note = isinstance(content, str) and content.strip() == REVIEW_END_SIGNAL

    return {
        "messages": [response],
        "turn_count": state["turn_count"] + 1,
        "should_generate_note": should_generate_note,
    }
