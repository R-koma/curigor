from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage

from graph.output_schemas import ExploreTurnAnalysis
from graph.state import LearningState


def _state(topic: str = "二分探索って何のためにあるの？") -> LearningState:
    base: dict[str, Any] = {
        "user_id": "user-1",
        "messages": [],
        "topic": topic,
        "turn_count": 0,
        "should_generate_note": False,
        "session_type": "explore",
    }
    return cast(LearningState, base)


async def _start(state: LearningState, analysis: ExploreTurnAnalysis | None) -> dict[str, Any]:
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="答えです", id="ai-1"))
    with (
        patch("graph.nodes._explore_dialogue.analyze_explore_turn", new=AsyncMock(return_value=analysis)),
        patch("graph.nodes._explore_dialogue.llm", mock_llm),
        patch("graph.nodes._explore_dialogue.load_image_blocks", new=AsyncMock(return_value=[])),
    ):
        from graph.nodes.explore_start import explore_start

        return await explore_start(state)


async def test_answers_the_first_utterance_right_away_with_a_short_topic() -> None:
    result = await _start(
        _state(),
        ExploreTurnAnalysis(user_intent="question", topic="二分探索", question_summary="二分探索の目的"),
    )

    user_message, answer = result["messages"]
    assert user_message.content == "二分探索って何のためにあるの？"
    assert answer.content == "答えです"
    assert "intake_card" not in answer.additional_kwargs
    assert result["topic"] == "二分探索"
    assert result["turn_count"] == 1
    assert result["explore_questions"] == [{"question": "二分探索の目的", "answer_message_id": "ai-1"}]
    assert result["wrap_up_offered"] is False
    assert result["end_confirmation"] is None


async def test_falls_back_to_the_utterance_as_the_topic_when_analysis_fails() -> None:
    utterance = "あ" * 80

    result = await _start(_state(utterance), None)

    assert result["topic"] == "あ" * 60
    assert result["messages"][1].content == "答えです"
