from typing import Any, cast
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from graph.state import DepthMapState, LearningState

MAP: DepthMapState = {
    "topic": "二分探索",
    "aspects": [
        {
            "id": "比較",
            "name": "真ん中との比較",
            "is_core": True,
            "defined_question": "q1",
            "reasoned_question": "q2",
            "applied_question": "q3",
        }
    ],
}


def _state(last: HumanMessage, **overrides: Any) -> LearningState:
    base: dict[str, Any] = {
        "user_id": "user-1",
        "messages": [HumanMessage("二分探索"), AIMessage("教材は？", additional_kwargs={"intake_card": {}}), last],
        "topic": "二分探索",
        "turn_count": 1,
        "should_generate_note": False,
        "session_type": "explore",
    }
    base.update(overrides)
    return cast(LearningState, base)


async def _run(state: LearningState, depth_map: DepthMapState | None = MAP) -> tuple[dict[str, Any], AsyncMock]:
    generate = AsyncMock(return_value=depth_map)
    with (
        patch("graph.nodes._explore_setup.generate_depth_map", new=generate),
        patch("graph.nodes._explore_setup.draft_overview", new=AsyncMock(return_value={"比較": "半分を捨てる"})),
    ):
        from graph.nodes._explore_setup import handle_explore_setup_turn

        return await handle_explore_setup_turn(state), generate


async def test_no_material_answer_leaves_the_source_empty() -> None:
    answer = HumanMessage("教材なし", additional_kwargs={"intake_answers": {"source": ["教材なし"]}})

    result, generate = await _run(_state(answer))

    assert result["learning_source"] == ""
    assert generate.call_args.kwargs["source"] == ""
    assert generate.call_args.kwargs["prior_knowledge"] == "ほとんど知らない（初めて学ぶ）"


async def test_card_answers_set_the_topic_and_material() -> None:
    answer = HumanMessage(
        "回答", additional_kwargs={"intake_answers": {"topic": "探索アルゴリズム", "source": ["入門書", "教材なし"]}}
    )

    result, _ = await _run(_state(answer))

    assert result["topic"] == "探索アルゴリズム"
    assert result["learning_source"] == "入門書"


async def test_free_text_reply_becomes_the_material() -> None:
    result, _ = await _run(_state(HumanMessage("大学の講義資料")))

    assert result["learning_source"] == "大学の講義資料"
    assert result["topic"] == "二分探索"


async def test_success_returns_the_overview_without_streaming() -> None:
    result, _ = await _run(_state(HumanMessage("教材なし", additional_kwargs={"intake_answers": {"source": []}})))

    message = result["messages"][0]
    assert message.additional_kwargs == {"explore_overview": True}
    assert "1. 真ん中との比較: 半分を捨てる" in message.content
    assert result["depth_map"] == MAP
    assert result["explore_overview"] == {"比較": "半分を捨てる"}
    assert result["explore_setup_failed"] is False
    assert result["explore_turn"] is None
    assert result["end_confirmation"] is None
    assert result["should_generate_note"] is False


async def test_failed_map_asks_for_the_topic_again() -> None:
    result, _ = await _run(_state(HumanMessage("教材なし")), depth_map=None)

    assert "depth_map" not in result
    assert result["explore_setup_failed"] is True
    assert result["messages"][0].additional_kwargs == {"explore_setup_failed": True}


async def test_after_a_failure_the_next_message_is_the_topic() -> None:
    state = _state(HumanMessage("線形探索"), explore_setup_failed=True, learning_source="入門書")

    result, generate = await _run(state)

    assert result["topic"] == "線形探索"
    assert generate.call_args.kwargs["topic"] == "線形探索"
    assert result["learning_source"] == "入門書"
