from typing import Any

from graph.nodes._explore_dialogue import prepare_explore_turn, respond_explore
from graph.nodes._explore_setup import handle_explore_setup_turn
from graph.state import LearningState


async def explore_dialogue(state: LearningState) -> dict[str, Any]:
    if not state.get("depth_map"):
        return await handle_explore_setup_turn(state)
    plan = await prepare_explore_turn(state)
    return await respond_explore(state, plan)


__all__ = ["explore_dialogue"]
