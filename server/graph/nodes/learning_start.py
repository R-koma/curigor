from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from graph.intake_card import build_intake_card, draft_intake_card, intake_lead
from graph.state import LearningState


async def learning_start(state: LearningState) -> dict[str, Any]:
    """学習フローの開始: 最初の発言からトピックを正規化し、聞き取りカードを返す。

    API から learning_goal（目的）が渡っていれば、カードから目的の質問を除く。
    """
    utterance = state["topic"]
    draft = await draft_intake_card(utterance)
    topic, card = build_intake_card(utterance, draft, ask_purpose=not state.get("learning_goal"))
    ask_topic = any(q.key == "topic" for q in card.questions)

    return {
        "messages": [
            HumanMessage(content=utterance),
            AIMessage(
                content=intake_lead(topic, ask_topic=ask_topic), additional_kwargs={"intake_card": card.model_dump()}
            ),
        ],
        "topic": topic,
        "turn_count": 1,
        "should_generate_note": False,
        "intake_complete": False,
        "intake_turns": 0,
    }


__all__ = ["learning_start"]
