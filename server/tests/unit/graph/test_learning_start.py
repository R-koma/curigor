from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from langchain_core.messages import AIMessage

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


class TestLearningStart:
    async def test_starts_intake_and_sets_turn_count(self) -> None:
        response = AIMessage(content="今回できるようになりたいことはありますか？")
        with patch("graph.nodes.learning_start.llm", MagicMock(ainvoke=AsyncMock(return_value=response))):
            from graph.nodes.learning_start import learning_start

            result = await learning_start(_state())

        assert result["turn_count"] == 1
        assert result["intake_complete"] is False
        assert result["intake_turns"] == 0
        assert result["should_generate_note"] is False
        assert result["messages"][0].content == "システムコール"
        assert result["messages"][1] is response

    async def test_preseeds_purpose_from_api_provided_learning_goal(self) -> None:
        response = AIMessage(content="出典はありますか？")
        mock_llm = MagicMock(ainvoke=AsyncMock(return_value=response))
        with patch("graph.nodes.learning_start.llm", mock_llm):
            from graph.nodes.learning_start import learning_start

            await learning_start(_state(learning_goal="面接対策"))

        prompt = mock_llm.ainvoke.call_args.args[0][0].content
        assert "面接対策" in prompt
        assert prompt.count("未回答") == 2
