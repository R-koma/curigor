import logging
from collections.abc import Sequence

from langchain_core.messages import SystemMessage

from graph.llm import INTERNAL_LLM_TAG, llm_structured
from graph.nodes._shared import recent_messages_block
from graph.output_schemas import (
    ExploreAnswersOutput,
    ExploreOverviewDraft,
    ExploreTermDraft,
    ExploreTermsOutput,
    ExploreTurnAnalysis,
)
from graph.prompts.explore import (
    EXPLORE_PROMPT_FINGERPRINT,
    build_explore_answers_prompt,
    build_explore_overview_prompt,
    build_explore_terms_prompt,
    build_explore_turn_analysis_prompt,
)
from graph.state import DepthMapState, LearningState

logger = logging.getLogger(__name__)

_METADATA = {"prompt_fingerprint": EXPLORE_PROMPT_FINGERPRINT}
_MAX_SUMMARY_LENGTH = 80


async def draft_overview(topic: str, depth_map: DepthMapState) -> dict[str, str]:
    runnable = llm_structured.with_structured_output(ExploreOverviewDraft, task="explore-overview").with_config(
        tags=[INTERNAL_LLM_TAG]
    )
    try:
        result = await runnable.ainvoke(
            [SystemMessage(content=build_explore_overview_prompt(topic=topic, depth_map=depth_map))],
            config={"run_name": "explore-overview", "metadata": _METADATA},
        )
    except Exception:
        logger.warning("explore overview generation failed", exc_info=True)
        return {}
    if not isinstance(result, ExploreOverviewDraft):
        return {}
    ids = {a["id"] for a in depth_map["aspects"]}
    return {s.aspect_id: s.summary.strip()[:_MAX_SUMMARY_LENGTH] for s in result.summaries if s.aspect_id in ids}


async def analyze_explore_turn(state: LearningState) -> ExploreTurnAnalysis | None:
    depth_map = state.get("depth_map")
    if not depth_map:
        return None
    prompt = build_explore_turn_analysis_prompt(
        topic=state["topic"],
        depth_map=depth_map,
        explained=state.get("explained_aspects") or [],
        recent_messages=recent_messages_block(state),
    )
    runnable = llm_structured.with_structured_output(ExploreTurnAnalysis, task="explore-turn-analysis").with_config(
        tags=[INTERNAL_LLM_TAG]
    )
    try:
        result = await runnable.ainvoke(
            [SystemMessage(content=prompt)], config={"run_name": "explore-turn-analysis", "metadata": _METADATA}
        )
    except Exception:
        logger.warning("explore turn analysis failed; answering as a question", exc_info=True)
        return None
    return result if isinstance(result, ExploreTurnAnalysis) else None


async def extract_terms(text: str) -> list[ExploreTermDraft]:
    runnable = llm_structured.with_structured_output(ExploreTermsOutput, task="extract-explore-terms")
    try:
        result = await runnable.ainvoke(
            [SystemMessage(content=build_explore_terms_prompt(text=text))],
            config={"run_name": "extract-explore-terms", "metadata": _METADATA},
        )
    except Exception:
        logger.warning("explore term extraction failed", exc_info=True)
        return []
    return list(result.terms) if isinstance(result, ExploreTermsOutput) else []


async def summarize_answers(pairs: Sequence[tuple[str, str]]) -> dict[int, str]:
    if not pairs:
        return {}
    runnable = llm_structured.with_structured_output(ExploreAnswersOutput, task="summarize-explore-answers")
    try:
        result = await runnable.ainvoke(
            [SystemMessage(content=build_explore_answers_prompt(pairs=pairs))],
            config={"run_name": "summarize-explore-answers", "metadata": _METADATA},
        )
    except Exception:
        logger.warning("explore answer summary failed; keeping questions without answers", exc_info=True)
        return {}
    if not isinstance(result, ExploreAnswersOutput):
        return {}
    return {a.index: a.answer.strip() for a in result.answers if 0 <= a.index < len(pairs)}
