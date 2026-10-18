from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from langchain_core.messages import HumanMessage

from graph.llm import INTERNAL_LLM_TAG
from graph.nodes._review_turn_analysis import analyze_review_turn
from graph.output_schemas import ReviewTurnAnalysis
from graph.prompts.review_turn_analysis import REVIEW_TURN_ANALYSIS_PROMPT, build_review_turn_analysis_prompt
from graph.review_progress import ReviewPointState, ReviewPointStatus
from graph.state import LearningState

_STATE = cast(
    LearningState,
    {
        "user_id": "user-abc",
        "dialogue_session_id": UUID("00000000-0000-0000-0000-000000000002"),
        "note_id": UUID("00000000-0000-0000-0000-000000000001"),
        "messages": [HumanMessage(content="半分に絞ります")],
        "topic": "二分探索",
        "turn_count": 2,
        "should_generate_note": False,
        "session_type": "review",
    },
)


async def _run(mock_invoke: AsyncMock) -> tuple[ReviewTurnAnalysis | None, MagicMock]:
    with_config = MagicMock(return_value=MagicMock(ainvoke=mock_invoke))
    mock_llm_structured = MagicMock()
    mock_llm_structured.with_structured_output.return_value.with_config = with_config
    with patch("graph.nodes._review_turn_analysis.llm_structured", mock_llm_structured):
        return await analyze_review_turn(_STATE), with_config


async def test_runnable_is_tagged_internal_and_named() -> None:
    invoke = AsyncMock(return_value=ReviewTurnAnalysis(wants_to_end_session=False))
    _, with_config = await _run(invoke)
    with_config.assert_called_once_with(tags=[INTERNAL_LLM_TAG])
    assert invoke.call_args.kwargs["config"] == {"run_name": "review-turn-analysis"}


async def test_exception_returns_none() -> None:
    result, _ = await _run(AsyncMock(side_effect=RuntimeError("boom")))
    assert result is None


async def test_unexpected_type_returns_none() -> None:
    result, _ = await _run(AsyncMock(return_value={"wants_to_end_session": True}))
    assert result is None


async def test_analysis_is_returned_as_is() -> None:
    analysis = ReviewTurnAnalysis(wants_to_end_session=True)
    result, _ = await _run(AsyncMock(return_value=analysis))
    assert result is analysis


def _plan_point(point_id: str, status: ReviewPointStatus = "pending") -> ReviewPointState:
    return {
        "id": point_id,
        "point": f"要点{point_id}",
        "question": f"質問{point_id}は？",
        "expected": [f"期待{point_id}a", f"期待{point_id}b"],
        "source": "general",
        "aspect_id": None,
        "in_note": True,
        "status": status,
        "queued": True,
    }


def test_analysis_prompt_without_points_is_unchanged() -> None:
    prompt = build_review_turn_analysis_prompt(topic="二分探索", recent_messages="ユーザー: 半分")
    assert prompt == REVIEW_TURN_ANALYSIS_PROMPT.format(topic="二分探索", recent_messages="ユーザー: 半分")


def test_analysis_prompt_lists_current_point_and_expected() -> None:
    prompt = build_review_turn_analysis_prompt(
        topic="二分探索",
        recent_messages="ユーザー: 半分",
        current_point=_plan_point("p1"),
        pending_points=[_plan_point("p2")],
    )
    assert "要点p1" in prompt
    assert "期待p1a" in prompt
    assert "current_point_explained" in prompt
    assert "p2: 要点p2" in prompt
    assert "期待p2b" in prompt


def test_analysis_prompt_for_the_opener_lists_pending_points_only() -> None:
    prompt = build_review_turn_analysis_prompt(
        topic="二分探索", recent_messages="ユーザー: 半分", pending_points=[_plan_point("p1"), _plan_point("p2")]
    )
    assert "p1: 要点p1" in prompt
    assert "p2: 要点p2" in prompt
    assert "current_point_explained" not in prompt


async def test_analysis_sends_the_current_and_pending_points_from_state() -> None:
    state = cast(
        LearningState,
        {
            **_STATE,
            "review_points": [_plan_point("p1", "explained"), _plan_point("p2", "hinted"), _plan_point("p3")],
            "review_current_point_id": "p2",
        },
    )
    invoke = AsyncMock(return_value=ReviewTurnAnalysis(wants_to_end_session=False))
    mock_llm_structured = MagicMock()
    mock_llm_structured.with_structured_output.return_value.with_config.return_value = MagicMock(ainvoke=invoke)
    with patch("graph.nodes._review_turn_analysis.llm_structured", mock_llm_structured):
        await analyze_review_turn(state)
    (messages,) = invoke.call_args.args
    prompt = messages[0].content
    assert "期待p2a" in prompt
    assert "p3: 要点p3" in prompt
    assert "p1: 要点p1" not in prompt
    assert "p2: 要点p2" not in prompt


async def test_analysis_on_the_opener_lists_every_pending_point() -> None:
    state = cast(LearningState, {**_STATE, "review_points": [_plan_point("p1"), _plan_point("p2")]})
    invoke = AsyncMock(return_value=ReviewTurnAnalysis(wants_to_end_session=False))
    mock_llm_structured = MagicMock()
    mock_llm_structured.with_structured_output.return_value.with_config.return_value = MagicMock(ainvoke=invoke)
    with patch("graph.nodes._review_turn_analysis.llm_structured", mock_llm_structured):
        await analyze_review_turn(state)
    (messages,) = invoke.call_args.args
    assert "p1: 要点p1" in messages[0].content
    assert "p2: 要点p2" in messages[0].content


def test_analysis_defaults_to_nothing_explained() -> None:
    analysis = ReviewTurnAnalysis(wants_to_end_session=False)
    assert analysis.current_point_explained is False
    assert analysis.explained_point_ids == []
