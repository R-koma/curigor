from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from graph.depth_map import build_depth_map
from graph.llm import INTERNAL_LLM_TAG
from graph.nodes._map_turn_analysis import analyze_map_dialogue_turn
from graph.output_schemas import DepthMapAspectDraft, MapAspectObservation, MapDialogueTurnAnalysis
from graph.state import LearningState, MapAspectProgress

_STATE = cast(
    LearningState,
    {
        "user_id": "user-abc",
        "dialogue_session_id": UUID("00000000-0000-0000-0000-000000000002"),
        "note_id": UUID("00000000-0000-0000-0000-000000000001"),
        "messages": [],
        "topic": "システムコール",
        "turn_count": 2,
        "should_generate_note": False,
        "session_type": "learning",
    },
)

_PLAN_FIELDS = {"learning_goal": "未指定", "focus_aspects": "未指定"}

_DEPTH_MAP = build_depth_map(
    "システムコール",
    [
        DepthMapAspectDraft(
            name="システムコールの定義",
            is_core=True,
            defined_question="定義できるか",
            reasoned_question="なぜ必要か",
            applied_question="どう活かすか",
        )
    ],
)
_ASPECT_ID = _DEPTH_MAP["aspects"][0]["id"]


async def _run(
    mock_invoke: AsyncMock,
    *,
    covered: list[MapAspectProgress] | None = None,
    with_config: MagicMock | None = None,
) -> MapDialogueTurnAnalysis | None:
    mock_runnable = MagicMock(ainvoke=mock_invoke)
    mock_llm_structured = MagicMock()
    mock_llm_structured.with_structured_output.return_value.with_config = with_config or MagicMock()
    mock_llm_structured.with_structured_output.return_value.with_config.return_value = mock_runnable
    with patch("graph.nodes._map_turn_analysis.llm_structured", mock_llm_structured):
        return await analyze_map_dialogue_turn(
            _STATE,
            recent_messages="ユーザー: システムコールとは…",
            plan_fields=_PLAN_FIELDS,
            depth_map=_DEPTH_MAP,
            map_covered=covered or [],
        )


class TestAnalyzeMapDialogueTurn:
    async def test_returns_analysis_on_success(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[MapAspectObservation(aspect_id=_ASPECT_ID, reached_stage="defined")],
            has_misconception=False,
            response_mode="deepen",
            selected_aspect_id=_ASPECT_ID,
        )
        result = await _run(AsyncMock(return_value=analysis))
        assert result is analysis

    async def test_returns_none_on_llm_failure(self) -> None:
        result = await _run(AsyncMock(side_effect=RuntimeError("llm down")))
        assert result is None

    async def test_prompt_lists_aspect_ids_and_topic(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[], has_misconception=False, response_mode="deepen", selected_aspect_id=_ASPECT_ID
        )
        mock_invoke = AsyncMock(return_value=analysis)
        await _run(mock_invoke)
        prompt = mock_invoke.call_args.args[0][0].content
        assert "システムコール" in prompt
        assert _ASPECT_ID in prompt
        assert mock_invoke.call_args.kwargs["config"]["run_name"] == "map-turn-analysis"

    async def test_a_flagged_misconception_forces_reinforce(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[],
            has_misconception=True,
            error_summary="誤り",
            response_mode="deepen",
            selected_aspect_id=_ASPECT_ID,
        )
        result = await _run(AsyncMock(return_value=analysis))
        assert result is not None
        assert result.response_mode == "reinforce"

    async def test_the_call_is_tagged_internal_so_it_is_not_streamed(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[], has_misconception=False, response_mode="deepen", selected_aspect_id=_ASPECT_ID
        )
        with_config = MagicMock()
        await _run(AsyncMock(return_value=analysis), with_config=with_config)
        with_config.assert_called_once_with(tags=[INTERNAL_LLM_TAG])

    async def test_returns_none_on_unexpected_payload(self) -> None:
        result = await _run(AsyncMock(return_value={"observations": []}))
        assert result is None

    async def test_prompt_carries_the_reasoned_guard_sentence(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[], has_misconception=False, response_mode="deepen", selected_aspect_id=_ASPECT_ID
        )
        mock_invoke = AsyncMock(return_value=analysis)
        await _run(mock_invoke)
        prompt = mock_invoke.call_args.args[0][0].content
        assert "日常の具体例を1つ挙げただけでは reasoned にしない" in prompt

    async def test_prompt_renders_the_coverage_line_when_covered(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[], has_misconception=False, response_mode="deepen", selected_aspect_id=_ASPECT_ID
        )
        mock_invoke = AsyncMock(return_value=analysis)
        await _run(mock_invoke, covered=[{"aspect_id": _ASPECT_ID, "reached_stage": "defined"}])
        prompt = mock_invoke.call_args.args[0][0].content
        assert "- システムコールの定義: defined（定義済み）" in prompt
        assert "（まだなし）" not in prompt

    async def test_prompt_shows_a_placeholder_when_nothing_is_covered(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[], has_misconception=False, response_mode="deepen", selected_aspect_id=_ASPECT_ID
        )
        mock_invoke = AsyncMock(return_value=analysis)
        await _run(mock_invoke)
        prompt = mock_invoke.call_args.args[0][0].content
        assert "（まだなし）" in prompt
        assert "- システムコールの定義: defined" not in prompt


class TestTopicCorrectionDetection:
    def test_corrected_topic_defaults_to_empty(self) -> None:
        from graph.output_schemas import MapDialogueTurnAnalysis

        analysis = MapDialogueTurnAnalysis(
            observations=[], has_misconception=False, response_mode="deepen", selected_aspect_id="a"
        )

        assert analysis.corrected_topic == ""

    def test_prompt_asks_to_judge_a_topic_correction_before_observations(self) -> None:
        from graph.depth_map import build_depth_map
        from graph.output_schemas import DepthMapAspectDraft
        from graph.prompts.map_turn_analysis import build_map_turn_analysis_prompt

        depth_map = build_depth_map(
            "この仕組み",
            [
                DepthMapAspectDraft(
                    name="仕組みの概要",
                    is_core=True,
                    defined_question="D",
                    reasoned_question="R",
                    applied_question="P",
                )
            ],
        )
        prompt = build_map_turn_analysis_prompt(
            topic="この仕組み",
            recent_messages="M",
            plan_fields={"learning_goal": "未指定", "focus_aspects": "未指定"},
            depth_map=depth_map,
            map_covered=[],
        )

        assert "`corrected_topic`" in prompt
        assert prompt.index("`corrected_topic`") < prompt.index("`observations`")
        assert "観点の話題が移っただけ" in prompt
