from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from graph.llm import llm
from graph.prompts.intake import build_intake_prompt
from graph.state import LearningState


async def learning_start(state: LearningState) -> dict[str, Any]:
    """学習フローの開始: topic のみで始め、聞き取り（目的・出典・前提知識）の最初の問いを返す。

    API から learning_goal（目的）が渡っていれば、聞き取りの対象からその項目を除外する。
    """
    topic = state["topic"]
    user_message = HumanMessage(content=topic)

    prompt = build_intake_prompt(
        topic=topic,
        purpose=state.get("learning_goal") or "",
        source="",
        prior_knowledge="",
        recent_messages="",
    )
    response = await llm.ainvoke([SystemMessage(content=prompt), user_message])

    return {
        "messages": [user_message, response],
        "turn_count": 1,
        "should_generate_note": False,
        "intake_complete": False,
        "intake_turns": 0,
    }


__all__ = ["learning_start"]
