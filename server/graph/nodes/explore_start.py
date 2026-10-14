from typing import Any, cast

from langchain_core.messages import HumanMessage

from graph.intake_card import MAX_TOPIC_LENGTH
from graph.nodes._explore_dialogue import prepare_explore_turn, respond_explore
from graph.state import LearningState


async def explore_start(state: LearningState) -> dict[str, Any]:
    utterance = state["topic"]
    first = HumanMessage(content=utterance)
    seeded = cast(
        LearningState,
        {
            **state,
            "messages": [first],
            "turn_count": 0,
            "explore_terms": [],
            "explore_questions": [],
            "wrap_up_offered": False,
            "end_confirmation": None,
        },
    )
    plan = await prepare_explore_turn(seeded)
    topic = (plan.topic or utterance.strip())[:MAX_TOPIC_LENGTH]
    result = await respond_explore(cast(LearningState, {**seeded, "topic": topic}), plan)
    return {**result, "messages": [first, *result.get("messages", [])], "topic": topic}


__all__ = ["explore_start"]
