from typing import cast
from unittest.mock import AsyncMock, patch
from uuid import UUID

from langchain_core.messages import AIMessage

from graph.output_schemas import IntakeCardDraft, IntakeOptionDraft
from graph.state import LearningState

SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
NOTE_ID = UUID("00000000-0000-0000-0000-000000000001")


def _state(**overrides: object) -> LearningState:
    base: dict[str, object] = {
        "user_id": "user-abc",
        "dialogue_session_id": SESSION_ID,
        "note_id": NOTE_ID,
        "messages": [],
        "topic": "システムコール",
        "turn_count": 0,
        "should_generate_note": False,
        "session_type": "learning",
    }
    base.update(overrides)
    return cast(LearningState, base)


def _draft() -> IntakeCardDraft:
    return IntakeCardDraft(
        topic="システムコール",
        purpose_options=[IntakeOptionDraft(label="面接対策"), IntakeOptionDraft(label="基礎を理解したい")],
        source_options=[IntakeOptionDraft(label="書籍"), IntakeOptionDraft(label="授業")],
        inferred_purpose="面接対策",
    )


class TestLearningStart:
    async def test_returns_intake_card_with_normalized_topic(self) -> None:
        with patch("graph.nodes.learning_start.draft_intake_card", AsyncMock(return_value=_draft())):
            from graph.nodes.learning_start import learning_start

            result = await learning_start(_state(topic="面接でシステムコールを聞かれるので学びたい"))

        assert result["topic"] == "システムコール"
        assert result["turn_count"] == 1
        assert result["intake_complete"] is False
        assert result["intake_turns"] == 0
        assert result["should_generate_note"] is False
        user_message, ai_message = result["messages"]
        assert user_message.content == "面接でシステムコールを聞かれるので学びたい"
        assert isinstance(ai_message, AIMessage)
        assert "システムコール" in ai_message.content
        card = ai_message.additional_kwargs["intake_card"]
        assert [q["key"] for q in card["questions"]] == ["purpose", "source", "prior_knowledge"]
        assert card["questions"][0]["preselected"] == ["面接対策"]

    async def test_starts_with_fallback_card_when_generation_fails(self) -> None:
        with patch("graph.nodes.learning_start.draft_intake_card", AsyncMock(return_value=None)):
            from graph.nodes.learning_start import learning_start

            result = await learning_start(_state())

        assert result["topic"] == "システムコール"
        assert result["intake_complete"] is False
        assert result["messages"][1].additional_kwargs["intake_card"]["questions"]

    async def test_omits_purpose_question_when_api_provided_learning_goal(self) -> None:
        with patch("graph.nodes.learning_start.draft_intake_card", AsyncMock(return_value=_draft())):
            from graph.nodes.learning_start import learning_start

            result = await learning_start(_state(learning_goal="面接対策"))

        keys = [q["key"] for q in result["messages"][1].additional_kwargs["intake_card"]["questions"]]
        assert keys == ["source", "prior_knowledge"]
