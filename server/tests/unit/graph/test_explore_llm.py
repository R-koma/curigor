from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import HumanMessage

from graph.llm import INTERNAL_LLM_TAG
from graph.nodes._explore_llm import analyze_explore_turn, draft_teachback_map, organize_memo
from graph.output_schemas import (
    DepthMapAspectDraft,
    DepthMapGeneration,
    ExploreMemoAspect,
    ExploreMemoOrganization,
    ExploreTurnAnalysis,
)
from graph.state import LearningState


def _draft(name: str, *, is_core: bool) -> DepthMapAspectDraft:
    return DepthMapAspectDraft(
        name=name, is_core=is_core, defined_question="d", reasoned_question="r", applied_question="a"
    )


async def _draft_map(result: Any = None, *, error: Exception | None = None) -> Any:
    invoke = AsyncMock(return_value=result, side_effect=error)
    llm = MagicMock()
    llm.with_structured_output.return_value = MagicMock(ainvoke=invoke)
    with patch("graph.nodes._explore_llm.llm_structured", llm):
        return await draft_teachback_map("二分探索", [("q", "a")], [])


async def test_teachback_map_is_none_without_aspects() -> None:
    assert await _draft_map(DepthMapGeneration(aspects=[])) is None


async def test_teachback_map_is_none_when_the_call_fails() -> None:
    assert await _draft_map(error=RuntimeError("boom")) is None


async def test_teachback_map_caps_core_aspects_at_four() -> None:
    result = DepthMapGeneration(aspects=[_draft(f"観点{i}", is_core=True) for i in range(5)])

    depth_map = await _draft_map(result)

    assert [a["is_core"] for a in depth_map["aspects"]] == [True, True, True, True, False]


async def test_teachback_map_promotes_the_first_aspect_when_none_is_core() -> None:
    result = DepthMapGeneration(aspects=[_draft("観点0", is_core=False), _draft("観点1", is_core=False)])

    depth_map = await _draft_map(result)

    assert [a["is_core"] for a in depth_map["aspects"]] == [True, False]


async def test_turn_analysis_call_is_tagged_internal_so_it_is_not_streamed() -> None:
    analysis = ExploreTurnAnalysis(user_intent="question", topic="二分探索", terms=[], question_summary="")
    with_config = MagicMock()
    with_config.return_value = MagicMock(ainvoke=AsyncMock(return_value=analysis))
    llm = MagicMock()
    llm.with_structured_output.return_value.with_config = with_config
    state = cast(LearningState, {"topic": "二分探索", "messages": [HumanMessage("二分探索って何？")]})

    with patch("graph.nodes._explore_llm.llm_structured", llm):
        assert await analyze_explore_turn(state) == analysis

    with_config.assert_called_once_with(tags=[INTERNAL_LLM_TAG])


async def _organize(result: Any = None, *, error: Exception | None = None) -> Any:
    invoke = AsyncMock(return_value=result, side_effect=error)
    llm = MagicMock()
    llm.with_structured_output.return_value = MagicMock(ainvoke=invoke)
    with patch("graph.nodes._explore_llm.llm_structured", llm):
        return await organize_memo("二分探索", [], [("q", "a")], [])


async def test_organize_memo_returns_the_structured_output() -> None:
    organization = ExploreMemoOrganization(
        summary="s", aspects=[ExploreMemoAspect(aspect_id="比較", summary="一行", question_indices=[0])]
    )

    assert await _organize(organization) == organization


async def test_organize_memo_is_none_when_the_output_is_not_an_organization() -> None:
    assert await _organize({"summary": "s", "aspects": []}) is None


async def test_organize_memo_is_none_when_the_call_fails() -> None:
    assert await _organize(error=RuntimeError("boom")) is None
