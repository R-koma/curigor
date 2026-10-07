from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from graph.output_schemas import ReviewTurnAnalysis
from graph.state import LearningState

SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
NOTE_ID = UUID("00000000-0000-0000-0000-000000000001")


def _make_state(**overrides: object) -> LearningState:
    base: dict[str, object] = {
        "user_id": "user-abc",
        "dialogue_session_id": SESSION_ID,
        "note_id": NOTE_ID,
        "messages": [HumanMessage(content="二分探索は半分に絞る手法です")],
        "topic": "二分探索",
        "turn_count": 2,
        "should_generate_note": False,
        "session_type": "review",
        "note_content": "二分探索のノート本文",
        "note_summary": "二分探索の要約",
    }
    base.update(overrides)
    return cast(LearningState, base)


def _no_end() -> Any:
    return patch(
        "graph.nodes.review_dialogue.analyze_review_turn",
        AsyncMock(return_value=ReviewTurnAnalysis(wants_to_end_session=False)),
    )


def _patched(analysis: ReviewTurnAnalysis | None) -> tuple[MagicMock, tuple[Any, Any]]:
    mock_llm = MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう")))
    return mock_llm, (
        patch("graph.nodes.review_dialogue.llm", mock_llm),
        patch("graph.nodes.review_dialogue.analyze_review_turn", AsyncMock(return_value=analysis)),
    )


async def _run(state: LearningState, analysis: ReviewTurnAnalysis | None) -> tuple[MagicMock, dict[str, object]]:
    mock_llm, (p_llm, p_analysis) = _patched(analysis=analysis)
    with p_llm, p_analysis:
        from graph.nodes.review_dialogue import review_dialogue

        return mock_llm, await review_dialogue(state)


class TestReviewEndSession:
    async def test_never_sets_should_generate_note(self) -> None:
        _, result = await _run(_make_state(), ReviewTurnAnalysis(wants_to_end_session=True))
        assert result["should_generate_note"] is False

    async def test_first_wish_to_end_offers_and_points_to_the_button(self) -> None:
        mock_llm, result = await _run(_make_state(), ReviewTurnAnalysis(wants_to_end_session=True))
        assert result["end_confirmation"] == "offered"
        (messages,) = mock_llm.ainvoke.call_args.args
        assert "下のボタン" in messages[0].content

    async def test_wish_to_end_after_an_offer_confirms_without_the_llm(self) -> None:
        mock_llm, result = await _run(
            _make_state(end_confirmation="offered"), ReviewTurnAnalysis(wants_to_end_session=True)
        )
        mock_llm.ainvoke.assert_not_called()
        assert result["end_confirmation"] == "confirmed"
        assert "messages" not in result

    async def test_an_answer_marks_the_review_as_answered_and_clears_the_offer(self) -> None:
        _, result = await _run(_make_state(end_confirmation="offered"), ReviewTurnAnalysis(wants_to_end_session=False))
        assert result["end_confirmation"] is None
        assert result["review_answered"] is True

    async def test_a_wish_to_end_alone_does_not_count_as_an_answer(self) -> None:
        _, result = await _run(_make_state(), ReviewTurnAnalysis(wants_to_end_session=True))
        assert result["review_answered"] is False

    async def test_analysis_failure_is_treated_as_an_answer(self) -> None:
        _, result = await _run(_make_state(end_confirmation="offered"), None)
        assert result["end_confirmation"] is None
        assert result["review_answered"] is True

    async def test_prompt_no_longer_mentions_the_end_signal(self) -> None:
        from graph.prompts import REVIEW_SYSTEM_PROMPT

        assert "LEARNING_END" not in REVIEW_SYSTEM_PROMPT


class TestReviewDialogue:
    async def test_uses_review_system_prompt(self) -> None:
        mock_llm = MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう")))
        with patch("graph.nodes.review_dialogue.llm", mock_llm), _no_end():
            from graph.nodes.review_dialogue import review_dialogue

            await review_dialogue(_make_state())

        (messages,) = mock_llm.ainvoke.call_args.args
        assert isinstance(messages[0], SystemMessage)
        assert "復習パートナー" in messages[0].content

    async def test_increments_turn_count(self) -> None:
        with (
            patch(
                "graph.nodes.review_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう"))),
            ),
            _no_end(),
        ):
            from graph.nodes.review_dialogue import review_dialogue

            result = await review_dialogue(_make_state(turn_count=2))

        assert result["turn_count"] == 3

    async def test_prior_improvements_injected_into_prompt(self) -> None:
        mock_llm = MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう")))
        with patch("graph.nodes.review_dialogue.llm", mock_llm), _no_end():
            from graph.nodes.review_dialogue import review_dialogue

            await review_dialogue(_make_state(prior_improvements="計算量の見積もりが曖昧でした"))

        (messages,) = mock_llm.ainvoke.call_args.args
        assert "重点確認項目" in messages[0].content
        assert "計算量の見積もりが曖昧でした" in messages[0].content

    async def test_focus_aspects_injected_into_prompt(self) -> None:
        mock_llm = MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう")))
        with patch("graph.nodes.review_dialogue.llm", mock_llm), _no_end():
            from graph.nodes.review_dialogue import review_dialogue

            await review_dialogue(_make_state(review_focus_aspects=["計算量"]))

        (messages,) = mock_llm.ainvoke.call_args.args
        assert "計算量" in messages[0].content

    async def test_no_prior_improvements_omits_focus_section(self) -> None:
        mock_llm = MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう")))
        with patch("graph.nodes.review_dialogue.llm", mock_llm), _no_end():
            from graph.nodes.review_dialogue import review_dialogue

            await review_dialogue(_make_state())

        (messages,) = mock_llm.ainvoke.call_args.args
        assert "重点確認項目" not in messages[0].content
