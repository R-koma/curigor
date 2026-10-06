import logging

from langchain_core.messages import SystemMessage

from graph.depth_map import build_depth_map
from graph.llm import INTERNAL_LLM_TAG, llm_structured
from graph.output_schemas import DepthMapGeneration
from graph.prompts.depth_map import build_depth_map_prompt
from graph.prompts.intake import INTAKE_PROMPT_FINGERPRINT
from graph.state import DepthMapState

logger = logging.getLogger(__name__)


async def generate_depth_map(*, topic: str, purpose: str, source: str, prior_knowledge: str) -> DepthMapState | None:
    prompt = build_depth_map_prompt(topic=topic, purpose=purpose, source=source, prior_knowledge=prior_knowledge)
    runnable = llm_structured.with_structured_output(DepthMapGeneration).with_config(tags=[INTERNAL_LLM_TAG])
    try:
        result = await runnable.ainvoke(
            [SystemMessage(content=prompt)],
            config={"run_name": "generate-depth-map", "metadata": {"prompt_fingerprint": INTAKE_PROMPT_FINGERPRINT}},
        )
    except Exception:
        logger.warning("depth map generation failed", exc_info=True)
        return None
    if not isinstance(result, DepthMapGeneration) or not result.aspects:
        logger.warning("depth map generation returned no aspects")
        return None
    return build_depth_map(topic, result.aspects)
