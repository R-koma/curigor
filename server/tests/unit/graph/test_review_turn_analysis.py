from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from langchain_core.messages import HumanMessage

from graph.llm import INTERNAL_LLM_TAG
from graph.nodes._review_turn_analysis import analyze_review_turn
from graph.output_schemas import ReviewTurnAnalysis
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
