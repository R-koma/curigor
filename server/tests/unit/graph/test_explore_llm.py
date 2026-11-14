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
        summary="s", aspects=[ExploreMemoAspect(aspect_id="比較", question_indices=[0])]
    )

    assert await _organize(organization) == organization


async def test_organize_memo_is_none_when_the_output_is_not_an_organization() -> None:
    assert await _organize({"summary": "s", "aspects": []}) is None


async def test_organize_memo_is_none_when_the_call_fails() -> None:
    assert await _organize(error=RuntimeError("boom")) is None


def _side_thread(quote: str) -> dict[str, Any]:
    from uuid import uuid4

    return {
        "id": uuid4(),
        "quote": quote,
        "messages": [{"role": "user", "content": f"{quote}とは？"}, {"role": "assistant", "content": "説明"}],
    }


async def _digest(threads: list[dict[str, Any]], result: Any = None, *, error: Exception | None = None) -> Any:
    from graph.nodes._explore_llm import digest_side_questions

    invoke = AsyncMock(return_value=result, side_effect=error)
    llm = MagicMock()
    llm.with_structured_output.return_value = MagicMock(ainvoke=invoke)
    with patch("graph.nodes._explore_llm.llm_structured", llm):
        digests = await digest_side_questions("インデックス", threads)
    return digests, invoke


async def test_digest_maps_items_to_threads_and_drops_unknown_indices() -> None:
    from graph.output_schemas import SideQuestionDigestItem, SideQuestionDigestOutput

    threads = [_side_thread("B木"), _side_thread("索引")]
    output = SideQuestionDigestOutput(
        items=[
            SideQuestionDigestItem(index=0, term=" B木 ", meaning="枝の多い木", question="", answer="無視"),
            SideQuestionDigestItem(index=1, question="なぜ速い", answer="探す範囲が狭まる"),
            SideQuestionDigestItem(index=5, question="範囲外"),
        ]
    )

    digests, invoke = await _digest(threads, output)

    first = digests[threads[0]["id"]]
    assert first.term is not None and first.term.term == "B木"
    assert (first.question, first.answer) == ("", "")
    second = digests[threads[1]["id"]]
    assert second.term is None
    assert (second.question, second.answer) == ("なぜ速い", "探す範囲が狭まる")
    assert len(digests) == 2
    prompt = invoke.call_args.args[0][0].content
    assert "[0] 選んだ箇所: 「B木」" in prompt
    assert invoke.call_args.kwargs["config"]["run_name"] == "digest-side-questions"


async def test_digest_failure_returns_nothing() -> None:
    digests, _ = await _digest([_side_thread("B木")], error=RuntimeError("boom"))

    assert digests == {}


async def test_digest_without_threads_does_not_call_the_llm() -> None:
    digests, invoke = await _digest([])

    assert digests == {}
    invoke.assert_not_awaited()
