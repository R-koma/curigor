from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from graph.explore_card import build_explore_card, explore_lead
from graph.intake_card import draft_intake_card
from graph.state import LearningState


async def explore_start(state: LearningState) -> dict[str, Any]:
    utterance = state["topic"]
    draft = await draft_intake_card(utterance)
    topic, card = build_explore_card(utterance, draft)
    ask_topic = any(q.key == "topic" for q in card.questions)
    return {
        "messages": [
            HumanMessage(content=utterance),
            AIMessage(
                content=explore_lead(topic, ask_topic=ask_topic), additional_kwargs={"intake_card": card.model_dump()}
            ),
        ],
        "topic": topic,
        "turn_count": 1,
        "should_generate_note": False,
        "explained_aspects": [],
        "explore_terms": [],
        "explore_questions": [],
        "wrap_up_offered": False,
    }


__all__ = ["explore_start"]
