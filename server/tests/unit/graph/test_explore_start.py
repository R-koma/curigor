from typing import Any, cast
from unittest.mock import AsyncMock, patch

from graph.output_schemas import IntakeCardDraft, IntakeOptionDraft
from graph.state import LearningState


def _state() -> LearningState:
    base: dict[str, Any] = {
        "user_id": "user-1",
        "messages": [],
        "topic": "二分探索を一から学びたい",
        "turn_count": 0,
        "should_generate_note": False,
        "session_type": "explore",
    }
    return cast(LearningState, base)


async def test_returns_the_material_card_and_empty_explore_records() -> None:
    draft = IntakeCardDraft(
        topic="二分探索",
        purpose_options=[IntakeOptionDraft(label="基礎"), IntakeOptionDraft(label="実務")],
        source_options=[IntakeOptionDraft(label="入門書"), IntakeOptionDraft(label="動画講座")],
    )
    with patch("graph.nodes.explore_start.draft_intake_card", new=AsyncMock(return_value=draft)):
        from graph.nodes.explore_start import explore_start

        result = await explore_start(_state())

    human, ai = result["messages"]
    assert human.content == "二分探索を一から学びたい"
    assert [q["key"] for q in ai.additional_kwargs["intake_card"]["questions"]] == ["source"]
    assert result["topic"] == "二分探索"
    assert result["explained_aspects"] == []
    assert result["explore_terms"] == []
    assert result["explore_questions"] == []
    assert result["should_generate_note"] is False
