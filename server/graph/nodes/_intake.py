"""聞き取り（目的・出典・前提知識）フェーズの処理。intake_complete=False のターンで呼ばれる。

完了ターンで地図生成が失敗した場合、`messages` を含まない dict を返す。
その場合は呼び出し元（learning_dialogue のルーター）が legacy 経路で応答を生成する
（このモジュールから legacy の prepare_turn/respond を呼ぶと learning_dialogue.py との
circular import になるため、responsibility を呼び出し元へ返す）。
"""

import logging
from typing import Any, cast

from langchain_core.messages import SystemMessage

from graph.depth_map import build_depth_map
from graph.llm import INTERNAL_LLM_TAG, llm, llm_structured
from graph.nodes._intake_analysis import extract_intake
from graph.nodes._map_dialogue import prepare_map_turn, respond_map
from graph.nodes._shared import recent_messages_block
from graph.output_schemas import DepthMapGeneration
from graph.prompts.depth_map import build_depth_map_prompt
from graph.prompts.intake import INTAKE_MAX_TURNS, build_intake_prompt
from graph.state import DepthMapState, LearningState

logger = logging.getLogger(__name__)


def _merge_field(existing: str | None, extracted: str) -> str:
    return extracted or (existing or "")


async def _generate_depth_map(*, topic: str, purpose: str, source: str, prior_knowledge: str) -> DepthMapState | None:
    prompt = build_depth_map_prompt(topic=topic, purpose=purpose, source=source, prior_knowledge=prior_knowledge)
    runnable = llm_structured.with_structured_output(DepthMapGeneration).with_config(tags=[INTERNAL_LLM_TAG])
    try:
        result = await runnable.ainvoke([SystemMessage(content=prompt)], config={"run_name": "generate-depth-map"})
    except Exception:
        logger.warning("depth map generation failed", exc_info=True)
        return None
    if not isinstance(result, DepthMapGeneration) or not result.aspects:
        logger.warning("depth map generation returned no aspects")
        return None
    return build_depth_map(topic, result.aspects)


async def handle_intake_turn(state: LearningState) -> dict[str, Any]:
    recent_messages = recent_messages_block(state)
    extraction = await extract_intake(state, recent_messages=recent_messages)

    purpose = _merge_field(state.get("learning_goal"), extraction.purpose if extraction else "")
    source = _merge_field(state.get("learning_source"), extraction.source if extraction else "")
    prior_knowledge = _merge_field(state.get("prior_knowledge"), extraction.prior_knowledge if extraction else "")
    turns = state.get("intake_turns", 0) + 1
    ready = bool(extraction and extraction.ready_to_start)
    complete = ready or turns >= INTAKE_MAX_TURNS or bool(purpose and source and prior_knowledge)

    base_updates: dict[str, Any] = {
        "intake_complete": complete,
        "intake_turns": turns,
        "learning_goal": purpose,
        "learning_source": source,
        "prior_knowledge": prior_knowledge,
        "turn_count": state["turn_count"] + 1,
        "should_generate_note": False,
    }

    if not complete:
        prompt = build_intake_prompt(
            topic=state["topic"],
            purpose=purpose,
            source=source,
            prior_knowledge=prior_knowledge,
            recent_messages=recent_messages,
        )
        response = await llm.ainvoke([SystemMessage(content=prompt)])
        return {**base_updates, "messages": [response]}

    depth_map = await _generate_depth_map(
        topic=state["topic"], purpose=purpose, source=source, prior_knowledge=prior_knowledge
    )
    if depth_map is None:
        return base_updates

    intake_message_count = len(state["messages"])
    first_turn_state = cast(
        LearningState,
        {
            **state,
            **base_updates,
            "turn_count": state["turn_count"],
            "depth_map": depth_map,
            "map_covered": [],
            "intake_message_count": intake_message_count,
        },
    )
    plan = await prepare_map_turn(first_turn_state)
    result = await respond_map(first_turn_state, plan)
    return {**base_updates, **result, "intake_message_count": intake_message_count}
