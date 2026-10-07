import logging

from langchain_core.messages import SystemMessage

from graph.llm import INTERNAL_LLM_TAG, llm_structured
from graph.nodes._shared import recent_messages_block
from graph.output_schemas import ReviewTurnAnalysis
from graph.prompts.review_turn_analysis import build_review_turn_analysis_prompt
from graph.state import LearningState

logger = logging.getLogger(__name__)


async def analyze_review_turn(state: LearningState) -> ReviewTurnAnalysis | None:
    prompt = build_review_turn_analysis_prompt(topic=state["topic"], recent_messages=recent_messages_block(state))
    runnable = llm_structured.with_structured_output(ReviewTurnAnalysis).with_config(tags=[INTERNAL_LLM_TAG])
    try:
        result = await runnable.ainvoke([SystemMessage(content=prompt)], config={"run_name": "review-turn-analysis"})
    except Exception:
        logger.warning("review turn analysis failed; treating the turn as an answer", exc_info=True)
        return None
    if not isinstance(result, ReviewTurnAnalysis):
        logger.warning("review turn analysis returned unexpected type %s", type(result).__name__)
        return None
    return result
