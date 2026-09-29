from typing import Any, cast
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage

from graph.nodes._shared import recent_messages_block
from graph.state import LearningState

SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
NOTE_ID = UUID("00000000-0000-0000-0000-000000000001")


def _state(messages: list[Any]) -> LearningState:
    return cast(
        LearningState,
        {
            "user_id": "user-abc",
            "dialogue_session_id": SESSION_ID,
            "note_id": NOTE_ID,
            "messages": messages,
            "topic": "二分探索",
            "turn_count": 2,
            "should_generate_note": False,
            "session_type": "learning",
        },
    )


class TestRecentMessagesBlock:
    def test_labels_human_and_ai_messages(self) -> None:
        messages = [HumanMessage(content="こんにちは"), AIMessage(content="こんにちは、始めましょう")]
        rendered = recent_messages_block(_state(messages))
        assert rendered == "ユーザー: こんにちは\nAI: こんにちは、始めましょう"

    def test_limits_to_last_n_messages(self) -> None:
        messages = [HumanMessage(content=f"m{i}") for i in range(8)]
        rendered = recent_messages_block(_state(messages), limit=6)
        assert "m2" in rendered and "m7" in rendered
        assert "m0" not in rendered and "m1" not in rendered

    def test_empty_messages_returns_empty_string(self) -> None:
        assert recent_messages_block(_state([])) == ""
