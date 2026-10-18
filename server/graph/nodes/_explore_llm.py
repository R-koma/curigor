import logging
from collections.abc import Sequence

from langchain_core.messages import SystemMessage

from graph.depth_map import build_depth_map
from graph.llm import INTERNAL_LLM_TAG, llm_structured
from graph.nodes._shared import recent_messages_block
from graph.output_schemas import (
    DepthMapGeneration,
    ExploreAnswersOutput,
    ExploreMemoOrganization,
    ExploreTermDraft,
    ExploreTermsOutput,
    ExploreTurnAnalysis,
)
from graph.prompts.explore import (
    EXPLORE_PROMPT_FINGERPRINT,
    build_explore_answers_prompt,
    build_explore_memo_organize_prompt,
    build_explore_teachback_map_prompt,
    build_explore_terms_prompt,
    build_explore_turn_analysis_prompt,
)
from graph.state import DepthMapAspectState, DepthMapState, ExploreTerm, LearningState

logger = logging.getLogger(__name__)

_METADATA = {"prompt_fingerprint": EXPLORE_PROMPT_FINGERPRINT}


async def analyze_explore_turn(state: LearningState) -> ExploreTurnAnalysis | None:
    prompt = build_explore_turn_analysis_prompt(topic=state["topic"], recent_messages=recent_messages_block(state))
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


async def draft_teachback_map(
    topic: str, pairs: Sequence[tuple[str, str]], terms: Sequence[ExploreTerm]
) -> DepthMapState | None:
    runnable = llm_structured.with_structured_output(DepthMapGeneration, task="explore-teachback-map")
    try:
        result = await runnable.ainvoke(
            [SystemMessage(content=build_explore_teachback_map_prompt(topic=topic, pairs=pairs, terms=terms))],
            config={"run_name": "explore-teachback-map", "metadata": _METADATA},
        )
    except Exception:
        logger.warning("explore teachback map generation failed", exc_info=True)
        return None
    if not isinstance(result, DepthMapGeneration) or not result.aspects:
        return None
    return build_depth_map(topic, result.aspects)


async def extract_terms(topic: str, text: str) -> list[ExploreTermDraft]:
    runnable = llm_structured.with_structured_output(ExploreTermsOutput, task="extract-explore-terms")
    try:
        result = await runnable.ainvoke(
            [SystemMessage(content=build_explore_terms_prompt(topic=topic, text=text))],
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


async def organize_memo(
    topic: str,
    aspects: Sequence[DepthMapAspectState],
    pairs: Sequence[tuple[str, str]],
    terms: Sequence[ExploreTerm],
) -> ExploreMemoOrganization | None:
    runnable = llm_structured.with_structured_output(ExploreMemoOrganization, task="organize-explore-memo")
    prompt = build_explore_memo_organize_prompt(topic=topic, aspects=aspects, pairs=pairs, terms=terms)
    try:
        result = await runnable.ainvoke(
            [SystemMessage(content=prompt)],
            config={"run_name": "organize-explore-memo", "metadata": _METADATA},
        )
    except Exception:
        logger.warning("explore memo organization failed", exc_info=True)
        return None
    return result if isinstance(result, ExploreMemoOrganization) else None
