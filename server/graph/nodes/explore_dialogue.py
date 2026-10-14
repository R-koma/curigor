from typing import Any

from graph.nodes._explore_dialogue import prepare_explore_turn, respond_explore
from graph.state import LearningState


async def explore_dialogue(state: LearningState) -> dict[str, Any]:
    plan = await prepare_explore_turn(state)
    return await respond_explore(state, plan)


__all__ = ["explore_dialogue"]
