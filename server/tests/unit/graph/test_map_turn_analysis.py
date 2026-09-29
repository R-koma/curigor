from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from graph.depth_map import build_depth_map
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
    mock_invoke: AsyncMock, *, covered: list[MapAspectProgress] | None = None
) -> MapDialogueTurnAnalysis | None:
    mock_runnable = MagicMock(ainvoke=mock_invoke)
    mock_llm_structured = MagicMock()
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
