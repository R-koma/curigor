from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage

from graph.output_schemas import IntakeExtraction
from graph.state import LearningState

SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
NOTE_ID = UUID("00000000-0000-0000-0000-000000000001")


def _make_state(messages: list[Any], **overrides: object) -> LearningState:
    base: dict[str, object] = {
        "user_id": "user-abc",
        "dialogue_session_id": SESSION_ID,
        "note_id": NOTE_ID,
        "messages": messages,
        "topic": "システムコール",
        "turn_count": 1,
        "should_generate_note": False,
        "session_type": "learning",
        "intake_complete": False,
        "intake_turns": 0,
    }
    base.update(overrides)
    return cast(LearningState, base)


class TestHandleIntakeTurnIncomplete:
    async def test_asks_the_next_question_when_fields_still_missing(self) -> None:
        extraction = IntakeExtraction(purpose="面接対策", source="", prior_knowledge="", ready_to_start=False)
        response = AIMessage(content="出典はありますか？")
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=extraction)),
            patch("graph.nodes._intake.llm", MagicMock(ainvoke=AsyncMock(return_value=response))),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(_make_state([HumanMessage(content="面接対策です")]))

        assert result["intake_complete"] is False
        assert result["intake_turns"] == 1
        assert result["learning_goal"] == "面接対策"
        assert result["messages"] == [response]

    async def test_extraction_failure_keeps_prior_values_and_does_not_crash(self) -> None:
        response = AIMessage(content="もう一度教えてください")
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=None)),
            patch("graph.nodes._intake.llm", MagicMock(ainvoke=AsyncMock(return_value=response))),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(
                _make_state([HumanMessage(content="わかりません")], learning_goal="面接対策")
            )

        assert result["learning_goal"] == "面接対策"
        assert result["intake_complete"] is False

    async def test_stops_after_reaching_the_turn_limit(self) -> None:
        extraction = IntakeExtraction(purpose="", source="", prior_knowledge="", ready_to_start=False)
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=extraction)),
            patch(
                "graph.nodes._intake._generate_depth_map",
                AsyncMock(
                    return_value={
                        "topic": "システムコール",
                        "aspects": [
                            {
                                "id": "a",
                                "name": "A",
                                "is_core": True,
                                "defined_question": "d",
                                "reasoned_question": "r",
                                "applied_question": "ap",
                            }
                        ],
                    }
                ),
            ),
            patch(
                "graph.nodes._intake.prepare_map_turn",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "graph.nodes._intake.respond_map",
                AsyncMock(return_value={"messages": [AIMessage(content="始めましょう")], "turn_count": 3}),
            ),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(_make_state([HumanMessage(content="特にありません")], intake_turns=2))

        assert result["intake_complete"] is True
        assert result["intake_turns"] == 3


class TestHandleIntakeTurnCompletion:
    async def test_all_three_fields_in_one_reply_completes_in_one_turn(self) -> None:
        """目的・出典・前提知識を一度に全部話した場合、聞き取りが1ターンで完了し1メッセージで返る。"""
        extraction = IntakeExtraction(
            purpose="面接対策", source="Linuxのしくみ", prior_knowledge="OSの授業を受けた", ready_to_start=False
        )
        map_response = {
            "messages": [AIMessage(content="では始めましょう")],
            "turn_count": 2,
            "depth_map": {"topic": "t", "aspects": []},
            "map_covered": [],
        }
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=extraction)),
            patch(
                "graph.nodes._intake._generate_depth_map",
                AsyncMock(
                    return_value={
                        "topic": "システムコール",
                        "aspects": [
                            {
                                "id": "a",
                                "name": "A",
                                "is_core": True,
                                "defined_question": "d",
                                "reasoned_question": "r",
                                "applied_question": "ap",
                            }
                        ],
                    }
                ),
            ),
            patch("graph.nodes._intake.prepare_map_turn", AsyncMock(return_value=MagicMock())),
            patch("graph.nodes._intake.respond_map", AsyncMock(return_value=map_response)),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(
                _make_state(
                    [HumanMessage(content="面接対策で、Linuxのしくみで学んでいて、OSの授業を受けたことがあります")]
                )
            )

        assert result["intake_complete"] is True
        assert result["intake_turns"] == 1
        assert result["messages"] == map_response["messages"]

    async def test_ready_to_start_completes_in_one_turn_and_returns_a_single_message(self) -> None:
        extraction = IntakeExtraction(purpose="面接対策", source="", prior_knowledge="", ready_to_start=True)
        map_response = {
            "messages": [AIMessage(content="では始めましょう")],
            "turn_count": 2,
            "depth_map": {"topic": "t", "aspects": []},
            "map_covered": [],
        }
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=extraction)),
            patch(
                "graph.nodes._intake._generate_depth_map",
                AsyncMock(
                    return_value={
                        "topic": "システムコール",
                        "aspects": [
                            {
                                "id": "a",
                                "name": "A",
                                "is_core": True,
                                "defined_question": "d",
                                "reasoned_question": "r",
                                "applied_question": "ap",
                            }
                        ],
                    }
                ),
            ),
            patch("graph.nodes._intake.prepare_map_turn", AsyncMock(return_value=MagicMock())),
            patch("graph.nodes._intake.respond_map", AsyncMock(return_value=map_response)),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(_make_state([HumanMessage(content="特に無いので始めたいです")]))

        assert result["intake_complete"] is True
        assert result["messages"] == map_response["messages"]

    async def test_depth_map_generation_failure_returns_no_messages_key(self) -> None:
        extraction = IntakeExtraction(purpose="面接対策", source="本", prior_knowledge="なし", ready_to_start=False)
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=extraction)),
            patch("graph.nodes._intake._generate_depth_map", AsyncMock(return_value=None)),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(_make_state([HumanMessage(content="本で勉強してます")]))

        assert result["intake_complete"] is True
        assert "messages" not in result
