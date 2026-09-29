"""地図駆動の学習対話 1 ターンの事前分析（観測 + 応答モード決定）。graph/nodes/_turn_analysis.py の地図版。"""

import logging

from langchain_core.messages import SystemMessage

from graph.llm import INTERNAL_LLM_TAG, llm_structured
from graph.output_schemas import MapDialogueTurnAnalysis
from graph.prompts.map_turn_analysis import build_map_turn_analysis_prompt
from graph.state import DepthMapState, LearningState, MapAspectProgress

logger = logging.getLogger(__name__)


async def analyze_map_dialogue_turn(
    state: LearningState,
    *,
    recent_messages: str,
    plan_fields: dict[str, str],
    depth_map: DepthMapState,
    map_covered: list[MapAspectProgress],
) -> MapDialogueTurnAnalysis | None:
    prompt = build_map_turn_analysis_prompt(
        topic=state["topic"],
        recent_messages=recent_messages,
        plan_fields=plan_fields,
        depth_map=depth_map,
        map_covered=map_covered,
    )
    runnable = llm_structured.with_structured_output(MapDialogueTurnAnalysis).with_config(tags=[INTERNAL_LLM_TAG])
    try:
        result = await runnable.ainvoke([SystemMessage(content=prompt)], config={"run_name": "map-turn-analysis"})
    except Exception:
        logger.warning("map turn analysis failed; falling back", exc_info=True)
        return None
    if not isinstance(result, MapDialogueTurnAnalysis):
        logger.warning("map turn analysis returned unexpected type %s", type(result).__name__)
        return None
    return _with_mode_from_misconception(result)


def _with_mode_from_misconception(analysis: MapDialogueTurnAnalysis) -> MapDialogueTurnAnalysis:
    if not analysis.has_misconception or analysis.response_mode == "reinforce":
        return analysis
    logger.warning("map turn analysis flagged a misconception but chose %s; forcing reinforce", analysis.response_mode)
    return analysis.model_copy(update={"response_mode": "reinforce"})
