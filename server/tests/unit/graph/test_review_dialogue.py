from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

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


class TestReviewDialogue:
    async def test_uses_review_system_prompt(self) -> None:
        mock_llm = MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう")))
        with patch("graph.nodes.review_dialogue.llm", mock_llm):
            from graph.nodes.review_dialogue import review_dialogue

            await review_dialogue(_make_state())

        (messages,) = mock_llm.ainvoke.call_args.args
        assert isinstance(messages[0], SystemMessage)
        assert "復習パートナー" in messages[0].content

    async def test_increments_turn_count(self) -> None:
        with patch(
            "graph.nodes.review_dialogue.llm",
            MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう"))),
        ):
            from graph.nodes.review_dialogue import review_dialogue

            result = await review_dialogue(_make_state(turn_count=2))

        assert result["turn_count"] == 3

    async def test_end_signal_sets_should_generate_note_true(self) -> None:
        with patch(
            "graph.nodes.review_dialogue.llm",
            MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="LEARNING_END"))),
        ):
            from graph.nodes.review_dialogue import review_dialogue

            result = await review_dialogue(_make_state())

        assert result["should_generate_note"] is True

    async def test_normal_text_sets_should_generate_note_false(self) -> None:
        with patch(
            "graph.nodes.review_dialogue.llm",
            MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="もう少し説明してください"))),
        ):
            from graph.nodes.review_dialogue import review_dialogue

            result = await review_dialogue(_make_state())

        assert result["should_generate_note"] is False

    async def test_prior_improvements_injected_into_prompt(self) -> None:
        mock_llm = MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう")))
        with patch("graph.nodes.review_dialogue.llm", mock_llm):
            from graph.nodes.review_dialogue import review_dialogue

            await review_dialogue(_make_state(prior_improvements="計算量の見積もりが曖昧でした"))

        (messages,) = mock_llm.ainvoke.call_args.args
        assert "重点確認項目" in messages[0].content
        assert "計算量の見積もりが曖昧でした" in messages[0].content

    async def test_focus_aspects_injected_into_prompt(self) -> None:
        mock_llm = MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう")))
        with patch("graph.nodes.review_dialogue.llm", mock_llm):
            from graph.nodes.review_dialogue import review_dialogue

            await review_dialogue(_make_state(review_focus_aspects=["計算量"]))

        (messages,) = mock_llm.ainvoke.call_args.args
        assert "計算量" in messages[0].content

    async def test_no_prior_improvements_omits_focus_section(self) -> None:
        mock_llm = MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう")))
        with patch("graph.nodes.review_dialogue.llm", mock_llm):
            from graph.nodes.review_dialogue import review_dialogue

            await review_dialogue(_make_state())

        (messages,) = mock_llm.ainvoke.call_args.args
        assert "重点確認項目" not in messages[0].content
