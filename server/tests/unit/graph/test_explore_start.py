from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage

from graph.output_schemas import ExploreTurnAnalysis
from graph.state import ExploreGap, LearningState

GAP = ExploreGap(
    note_id="note-1",
    feedback_id="feedback-1",
    improvement_index=0,
    improvement="境界の扱いが曖昧",
    note_content="二分探索は、ソート済みの配列を半分ずつ絞り込んで探す方法。",
    aspect_id="a1",
    aspect_name="境界条件",
)


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


async def _start(
    state: LearningState,
    analysis: ExploreTurnAnalysis | None,
    mock_llm: MagicMock | None = None,
    analyze: AsyncMock | None = None,
) -> dict[str, Any]:
    if mock_llm is None:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="答えです", id="ai-1"))
    with (
        patch("graph.nodes._explore_dialogue.analyze_explore_turn", new=analyze or AsyncMock(return_value=analysis)),
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


async def test_gap_start_skips_turn_analysis_and_keeps_the_note_topic() -> None:
    state = cast(LearningState, {**_state("二分探索"), "explore_gap": GAP})
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="境界はこう扱います", id="ai-1"))
    analyze = AsyncMock()

    result = await _start(state, None, mock_llm, analyze)

    analyze.assert_not_awaited()
    assert result["topic"] == "二分探索"
    assert result["explore_questions"] == [
        {"question": "「境界の扱いが曖昧」と指摘された部分は、どういうことか", "answer_message_id": "ai-1"}
    ]
    user_message, answer = result["messages"]
    assert user_message.content == "改善点「境界の扱いが曖昧」を理解したい"
    assert answer.content == "境界はこう扱います"
    system_prompt = mock_llm.ainvoke.await_args.args[0][0].content
    assert "改善点の内容を教える" in system_prompt
    assert "境界の扱いが曖昧" in system_prompt
