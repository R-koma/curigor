from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from graph.nodes._intake_analysis import extract_intake
from graph.output_schemas import IntakeExtraction
from graph.state import LearningState

_STATE = cast(
    LearningState,
    {
        "user_id": "user-abc",
        "dialogue_session_id": UUID("00000000-0000-0000-0000-000000000002"),
        "note_id": UUID("00000000-0000-0000-0000-000000000001"),
        "messages": [],
        "topic": "システムコール",
        "turn_count": 1,
        "should_generate_note": False,
        "session_type": "learning",
    },
)


async def _run(mock_invoke: AsyncMock) -> IntakeExtraction | None:
    mock_runnable = MagicMock(ainvoke=mock_invoke)
    mock_llm_structured = MagicMock()
    mock_llm_structured.with_structured_output.return_value.with_config.return_value = mock_runnable
    with patch("graph.nodes._intake_analysis.llm_structured", mock_llm_structured):
        return await extract_intake(_STATE, recent_messages="ユーザー: 面接対策です")


class TestExtractIntake:
    async def test_returns_extraction_on_success(self) -> None:
        extraction = IntakeExtraction(purpose="面接対策", source="", prior_knowledge="")
        result = await _run(AsyncMock(return_value=extraction))
        assert result is extraction

    async def test_tags_the_call_with_the_intake_prompt_fingerprint(self) -> None:
        from graph.prompts.intake import INTAKE_PROMPT_FINGERPRINT

        invoke = AsyncMock(return_value=IntakeExtraction())
        await _run(invoke)

        config = invoke.call_args.kwargs["config"]
        assert config["run_name"] == "extract-intake"
        assert config["metadata"]["prompt_fingerprint"] == INTAKE_PROMPT_FINGERPRINT

    async def test_returns_none_on_llm_failure(self) -> None:
        result = await _run(AsyncMock(side_effect=RuntimeError("llm down")))
        assert result is None

    async def test_returns_none_on_unexpected_payload(self) -> None:
        result = await _run(AsyncMock(return_value={"purpose": "面接対策"}))
        assert result is None

    async def test_prompt_includes_topic_and_history(self) -> None:
        extraction = IntakeExtraction(purpose="", source="", prior_knowledge="")
        mock_invoke = AsyncMock(return_value=extraction)
        await _run(mock_invoke)
        prompt = mock_invoke.call_args.args[0][0].content
        assert "システムコール" in prompt
        assert "面接対策です" in prompt
        assert mock_invoke.call_args.kwargs["config"]["run_name"] == "extract-intake"
