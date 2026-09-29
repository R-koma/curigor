from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage

from graph.llm import INTERNAL_LLM_TAG
from graph.output_schemas import DepthMapAspectDraft, DepthMapGeneration, IntakeExtraction
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

    async def test_extraction_failure_on_a_fresh_state_leaves_all_fields_empty(self) -> None:
        response = AIMessage(content="目的を教えてください")
        mock_llm = MagicMock(ainvoke=AsyncMock(return_value=response))
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=None)),
            patch("graph.nodes._intake.llm", mock_llm),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(_make_state([HumanMessage(content="うーん")]))

        assert result["learning_goal"] == ""
        assert result["learning_source"] == ""
        assert result["prior_knowledge"] == ""
        assert result["intake_complete"] is False
        mock_llm.ainvoke.assert_awaited_once()
        assert result["messages"] == [response]

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
        assert result["intake_turns"] == 1
        assert result["learning_goal"] == "面接対策"
        assert result["turn_count"] == 2
        assert result["should_generate_note"] is False

    async def test_map_success_passes_the_original_turn_count_to_respond_map(self) -> None:
        extraction = IntakeExtraction(purpose="面接対策", source="本", prior_knowledge="なし", ready_to_start=False)
        depth_map = {"topic": "システムコール", "aspects": []}
        map_response = {
            "messages": [AIMessage(content="では始めましょう")],
            "turn_count": 99,
            "depth_map": {"topic": "respond", "aspects": []},
            "map_covered": [],
        }
        prepare = AsyncMock(return_value=MagicMock())
        respond = AsyncMock(return_value=map_response)
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=extraction)),
            patch("graph.nodes._intake._generate_depth_map", AsyncMock(return_value=depth_map)),
            patch("graph.nodes._intake.prepare_map_turn", prepare),
            patch("graph.nodes._intake.respond_map", respond),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(_make_state([HumanMessage(content="本で")], turn_count=4))

        for passed in (prepare.call_args.args[0], respond.call_args.args[0]):
            assert passed["turn_count"] == 4
            assert passed["depth_map"] == depth_map
            assert passed["map_covered"] == []
            assert passed["learning_goal"] == "面接対策"
        assert result["turn_count"] == 99
        assert result["depth_map"] == {"topic": "respond", "aspects": []}
        assert result["messages"] == map_response["messages"]


_DRAFT = DepthMapAspectDraft(
    name="システムコールの定義",
    is_core=True,
    defined_question="定義できるか",
    reasoned_question="なぜ必要か",
    applied_question="どう活かすか",
)


async def _run_generate(mock_invoke: AsyncMock) -> tuple[Any, MagicMock]:
    mock_llm_structured = MagicMock()
    with_config = mock_llm_structured.with_structured_output.return_value.with_config
    with_config.return_value = MagicMock(ainvoke=mock_invoke)
    with patch("graph.nodes._intake.llm_structured", mock_llm_structured):
        from graph.nodes._intake import _generate_depth_map

        result = await _generate_depth_map(
            topic="システムコール", purpose="面接対策", source="本", prior_knowledge="なし"
        )
    return result, with_config


class TestGenerateDepthMap:
    async def test_returns_a_depth_map_for_a_valid_generation(self) -> None:
        result, _ = await _run_generate(AsyncMock(return_value=DepthMapGeneration(aspects=[_DRAFT])))
        assert result is not None
        assert result["topic"] == "システムコール"
        assert [a["name"] for a in result["aspects"]] == ["システムコールの定義"]
        assert result["aspects"][0]["is_core"] is True

    async def test_returns_none_for_an_empty_aspect_list(self) -> None:
        result, _ = await _run_generate(AsyncMock(return_value=DepthMapGeneration(aspects=[])))
        assert result is None

    async def test_returns_none_on_llm_failure(self) -> None:
        result, _ = await _run_generate(AsyncMock(side_effect=RuntimeError("llm down")))
        assert result is None

    async def test_returns_none_on_unexpected_payload(self) -> None:
        result, _ = await _run_generate(AsyncMock(return_value={"aspects": []}))
        assert result is None

    async def test_is_tagged_internal_and_named_for_tracing(self) -> None:
        mock_invoke = AsyncMock(return_value=DepthMapGeneration(aspects=[_DRAFT]))
        _, with_config = await _run_generate(mock_invoke)
        with_config.assert_called_once_with(tags=[INTERNAL_LLM_TAG])
        assert mock_invoke.call_args.kwargs["config"]["run_name"] == "generate-depth-map"
