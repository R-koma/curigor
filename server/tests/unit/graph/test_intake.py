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
            patch("graph.nodes._intake.llm", _kickoff_llm()),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(_make_state([HumanMessage(content="特にありません")], intake_turns=2))

        assert result["intake_complete"] is True
        assert result["intake_turns"] == 3


_MAP: Any = {"topic": "システムコール", "aspects": []}


def _kickoff_llm(text: str = "ここから学習を始めましょう") -> MagicMock:
    return MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content=text)))


class TestHandleIntakeTurnCompletion:
    async def _complete(
        self,
        extraction: IntakeExtraction,
        messages: list[Any],
        kickoff: MagicMock,
        **overrides: object,
    ) -> dict[str, Any]:
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=extraction)),
            patch("graph.nodes._intake._generate_depth_map", AsyncMock(return_value=_MAP)),
            patch("graph.nodes._intake.llm", kickoff),
        ):
            from graph.nodes._intake import handle_intake_turn

            return await handle_intake_turn(_make_state(messages, **overrides))

    async def test_all_three_fields_in_one_reply_completes_in_one_turn(self) -> None:
        extraction = IntakeExtraction(
            purpose="面接対策", source="Linuxのしくみ", prior_knowledge="OSの授業を受けた", ready_to_start=False
        )
        kickoff = _kickoff_llm("では始めましょう")

        result = await self._complete(
            extraction,
            [HumanMessage(content="面接対策で、Linuxのしくみで学んでいて、OSの授業を受けたことがあります")],
            kickoff,
        )

        assert result["intake_complete"] is True
        assert result["intake_turns"] == 1
        assert [m.content for m in result["messages"]] == ["では始めましょう"]

    async def test_ready_to_start_completes_in_one_turn_and_returns_a_single_message(self) -> None:
        extraction = IntakeExtraction(purpose="面接対策", source="", prior_knowledge="", ready_to_start=True)

        result = await self._complete(extraction, [HumanMessage(content="特に無いので始めたいです")], _kickoff_llm())

        assert result["intake_complete"] is True
        assert len(result["messages"]) == 1

    async def test_completion_turn_does_not_run_map_turn_analysis(self) -> None:
        extraction = IntakeExtraction(purpose="", source="本", prior_knowledge="なし", ready_to_start=True)
        analyze = AsyncMock()
        with patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", analyze):
            result = await self._complete(extraction, [HumanMessage(content="特にない")], _kickoff_llm())

        analyze.assert_not_called()
        assert result["turn_analysis"] is None
        assert result["wrap_up_offered"] is False

    async def test_kickoff_prompt_uses_only_answered_intake_fields(self) -> None:
        extraction = IntakeExtraction(
            purpose="", source="Linuxのしくみ", prior_knowledge="ほとんどない", ready_to_start=True
        )
        kickoff = _kickoff_llm()

        await self._complete(extraction, [HumanMessage(content="特にない")], kickoff)

        prompt = kickoff.ainvoke.call_args.args[0][0].content
        assert "Linuxのしくみ" in prompt
        assert "目的（何ができるようになりたいか）: 未回答" in prompt

    async def test_persists_depth_map_and_starts_with_no_coverage(self) -> None:
        extraction = IntakeExtraction(purpose="面接対策", source="本", prior_knowledge="なし", ready_to_start=False)

        result = await self._complete(extraction, [HumanMessage(content="本で")], _kickoff_llm(), turn_count=4)

        assert result["depth_map"] == _MAP
        assert result["map_covered"] == []
        assert result["turn_count"] == 5
        assert result["should_generate_note"] is False

    async def test_persists_intake_message_count_before_the_kickoff_message(self) -> None:
        extraction = IntakeExtraction(purpose="面接対策", source="本", prior_knowledge="なし", ready_to_start=False)
        messages = [AIMessage(content="前提は？"), HumanMessage(content="よくわからないです")]

        result = await self._complete(extraction, messages, _kickoff_llm())

        assert result["intake_message_count"] == 2

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
        assert "intake_message_count" not in result
        assert result["intake_turns"] == 1
        assert result["learning_goal"] == "面接対策"
        assert result["turn_count"] == 2
        assert result["should_generate_note"] is False


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
