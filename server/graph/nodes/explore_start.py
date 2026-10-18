from typing import Any, cast

from langchain_core.messages import HumanMessage

from graph.intake_card import MAX_TOPIC_LENGTH
from graph.nodes._explore_dialogue import ExploreTurnPlan, prepare_explore_turn, respond_explore
from graph.state import ExploreGap, LearningState
from services.explore_gap import gap_opening_utterance

_GAP_OPENING_PLAN = ExploreTurnPlan(
    user_intent="question", topic="", terms=[], question_summary="", wrap_up=False, end_confirmation=None
)


def _seed(state: LearningState, first: HumanMessage) -> LearningState:
    return cast(
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


async def _start_from_gap(state: LearningState, gap: ExploreGap) -> dict[str, Any]:
    first = HumanMessage(content=gap_opening_utterance(gap))
    result = await respond_explore(_seed(state, first), _GAP_OPENING_PLAN, gap_opening=True)
    return {**result, "messages": [first, *result.get("messages", [])], "topic": state["topic"]}


async def explore_start(state: LearningState) -> dict[str, Any]:
    gap = state.get("explore_gap")
    if gap is not None:
        return await _start_from_gap(state, gap)
    utterance = state["topic"]
    first = HumanMessage(content=utterance)
    seeded = _seed(state, first)
    plan = await prepare_explore_turn(seeded)
    topic = (plan.topic or utterance.strip())[:MAX_TOPIC_LENGTH]
    result = await respond_explore(cast(LearningState, {**seeded, "topic": topic}), plan)
    return {**result, "messages": [first, *result.get("messages", [])], "topic": topic}


__all__ = ["explore_start"]
