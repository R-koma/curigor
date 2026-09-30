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


_MAP: Any = {"topic": "システムコール", "aspects": []}


def _kickoff_llm(text: str = "ここから学習を始めましょう") -> MagicMock:
    return MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content=text)))


def _answers_message(purpose: str = "", source: list[str] | None = None, prior_knowledge: str = "") -> HumanMessage:
    return HumanMessage(
        content="回答",
        additional_kwargs={
            "intake_answers": {"purpose": purpose, "source": source or [], "prior_knowledge": prior_knowledge}
        },
    )


class TestHandleIntakeTurnWithCardAnswers:
    async def _run(self, messages: list[Any], **overrides: object) -> tuple[dict[str, Any], AsyncMock]:
        extract = AsyncMock()
        with (
            patch("graph.nodes._intake.extract_intake", extract),
            patch("graph.nodes._intake._generate_depth_map", AsyncMock(return_value=_MAP)),
            patch("graph.nodes._intake.llm", _kickoff_llm()),
        ):
            from graph.nodes._intake import handle_intake_turn

            return await handle_intake_turn(_make_state(messages, **overrides)), extract

    async def test_tags_the_kickoff_with_the_intake_prompt_fingerprint(self) -> None:
        from graph.nodes._intake import handle_intake_turn
        from graph.prompts.intake import INTAKE_PROMPT_FINGERPRINT

        kickoff = _kickoff_llm()
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock()),
            patch("graph.nodes._intake._generate_depth_map", AsyncMock(return_value=_MAP)),
            patch("graph.nodes._intake.llm", kickoff),
        ):
            await handle_intake_turn(_make_state([_answers_message(purpose="面接対策")]))

        metadata = kickoff.ainvoke.call_args.kwargs["config"]["metadata"]
        assert metadata["prompt_fingerprint"] == INTAKE_PROMPT_FINGERPRINT

    async def test_uses_card_answers_without_extraction(self) -> None:
        result, extract = await self._run(
            [_answers_message("仕事で使う", ["公式ドキュメント", "Udemy"], "聞いたことはある")]
        )

        extract.assert_not_called()
        assert result["intake_complete"] is True
        assert result["learning_goal"] == "仕事で使う"
        assert result["learning_source"] == "公式ドキュメント、Udemy"
        assert result["prior_knowledge"] == "聞いたことはある"

    async def test_all_skipped_still_completes(self) -> None:
        result, _ = await self._run([_answers_message()])

        assert result["intake_complete"] is True
        assert result["learning_goal"] == ""
        assert len(result["messages"]) == 1

    async def test_api_provided_goal_is_kept_when_purpose_was_not_asked(self) -> None:
        result, _ = await self._run([_answers_message(source=["書籍"])], learning_goal="面接対策")

        assert result["learning_goal"] == "面接対策"


class TestHandleIntakeTurnWithFreeText:
    async def test_free_text_reply_completes_in_one_turn(self) -> None:
        extraction = IntakeExtraction(purpose="面接対策", source="", prior_knowledge="")
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=extraction)),
            patch("graph.nodes._intake._generate_depth_map", AsyncMock(return_value=_MAP)),
            patch("graph.nodes._intake.llm", _kickoff_llm()),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(_make_state([HumanMessage(content="面接対策です")]))

        assert result["intake_complete"] is True
        assert result["intake_turns"] == 1
        assert result["learning_goal"] == "面接対策"

    async def test_extraction_failure_still_completes_with_prior_values(self) -> None:
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=None)),
            patch("graph.nodes._intake._generate_depth_map", AsyncMock(return_value=_MAP)),
            patch("graph.nodes._intake.llm", _kickoff_llm()),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(
                _make_state([HumanMessage(content="わかりません")], learning_goal="面接対策")
            )

        assert result["intake_complete"] is True
        assert result["learning_goal"] == "面接対策"


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
        extraction = IntakeExtraction(purpose="面接対策", source="Linuxのしくみ", prior_knowledge="OSの授業を受けた")
        kickoff = _kickoff_llm("では始めましょう")

        result = await self._complete(
            extraction,
            [HumanMessage(content="面接対策で、Linuxのしくみで学んでいて、OSの授業を受けたことがあります")],
            kickoff,
        )

        assert result["intake_complete"] is True
        assert result["intake_turns"] == 1
        assert [m.content for m in result["messages"]] == ["では始めましょう"]

    async def test_completion_turn_does_not_run_map_turn_analysis(self) -> None:
        extraction = IntakeExtraction(purpose="", source="本", prior_knowledge="なし")
        analyze = AsyncMock()
        with patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", analyze):
            result = await self._complete(extraction, [HumanMessage(content="特にない")], _kickoff_llm())

        analyze.assert_not_called()
        assert result["turn_analysis"] is None
        assert result["wrap_up_offered"] is False

    async def test_kickoff_prompt_uses_only_answered_intake_fields(self) -> None:
        extraction = IntakeExtraction(purpose="", source="Linuxのしくみ", prior_knowledge="ほとんどない")
        kickoff = _kickoff_llm()

        await self._complete(extraction, [HumanMessage(content="特にない")], kickoff)

        prompt = kickoff.ainvoke.call_args.args[0][0].content
        assert "Linuxのしくみ" in prompt
        assert "目的（何ができるようになりたいか）: 未回答" in prompt

    async def test_persists_depth_map_and_starts_with_no_coverage(self) -> None:
        extraction = IntakeExtraction(purpose="面接対策", source="本", prior_knowledge="なし")

        result = await self._complete(extraction, [HumanMessage(content="本で")], _kickoff_llm(), turn_count=4)

        assert result["depth_map"] == _MAP
        assert result["map_covered"] == []
        assert result["turn_count"] == 5
        assert result["should_generate_note"] is False

    async def test_persists_intake_message_count_before_the_kickoff_message(self) -> None:
        extraction = IntakeExtraction(purpose="面接対策", source="本", prior_knowledge="なし")
        messages = [AIMessage(content="前提は？"), HumanMessage(content="よくわからないです")]

        result = await self._complete(extraction, messages, _kickoff_llm())

        assert result["intake_message_count"] == 2

    async def test_depth_map_generation_failure_returns_no_messages_key(self) -> None:
        extraction = IntakeExtraction(purpose="面接対策", source="本", prior_knowledge="なし")
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

    async def test_tags_the_call_with_the_intake_prompt_fingerprint(self) -> None:
        from graph.prompts.intake import INTAKE_PROMPT_FINGERPRINT

        invoke = AsyncMock(return_value=DepthMapGeneration(aspects=[_DRAFT]))
        await _run_generate(invoke)

        config = invoke.call_args.kwargs["config"]
        assert config["run_name"] == "generate-depth-map"
        assert config["metadata"]["prompt_fingerprint"] == INTAKE_PROMPT_FINGERPRINT

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
