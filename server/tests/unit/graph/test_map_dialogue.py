from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage

from graph.depth_map import build_depth_map
from graph.output_schemas import DepthMapAspectDraft, MapAspectObservation, MapDialogueTurnAnalysis
from graph.state import LearningState, MapAspectProgress

SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
NOTE_ID = UUID("00000000-0000-0000-0000-000000000001")

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

_FAKE_PROMPT = MagicMock(return_value=("QUESTION_PROMPT", "dialogue"))
_NO_ANALYSIS = AsyncMock(return_value=None)


def _make_state(messages: list[Any], **overrides: object) -> LearningState:
    base: dict[str, object] = {
        "user_id": "user-abc",
        "dialogue_session_id": SESSION_ID,
        "note_id": NOTE_ID,
        "messages": messages,
        "topic": "システムコール",
        "turn_count": 2,
        "should_generate_note": False,
        "session_type": "learning",
        "depth_map": _DEPTH_MAP,
    }
    base.update(overrides)
    return cast(LearningState, base)


class TestPrepareMapTurn:
    async def test_merges_observations_into_map_covered(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[MapAspectObservation(aspect_id=_ASPECT_ID, reached_stage="defined")],
            has_misconception=False,
            response_mode="deepen",
            selected_aspect_id=_ASPECT_ID,
        )
        with patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", AsyncMock(return_value=analysis)):
            from graph.nodes._map_dialogue import prepare_map_turn

            plan = await prepare_map_turn(_make_state([HumanMessage(content="システムコールとは…")]))

        assert plan.map_covered == [{"aspect_id": _ASPECT_ID, "reached_stage": "defined"}]

    async def test_offers_wrap_up_when_core_aspects_reach_reasoned(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[MapAspectObservation(aspect_id=_ASPECT_ID, reached_stage="reasoned")],
            has_misconception=False,
            response_mode="expand",
            selected_aspect_id=_ASPECT_ID,
        )
        with patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", AsyncMock(return_value=analysis)):
            from graph.nodes._map_dialogue import prepare_map_turn

            plan = await prepare_map_turn(_make_state([HumanMessage(content="なぜカーネル経由か説明できます")]))

        assert plan.wrap_up is True

    async def test_analysis_failure_keeps_existing_coverage(self) -> None:
        existing: list[MapAspectProgress] = [{"aspect_id": _ASPECT_ID, "reached_stage": "defined"}]
        with patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", _NO_ANALYSIS):
            from graph.nodes._map_dialogue import prepare_map_turn

            plan = await prepare_map_turn(_make_state([HumanMessage(content="わかりません")], map_covered=existing))

        assert plan.map_covered == existing
        assert plan.wrap_up is False


class TestRespondMap:
    async def test_increments_turn_count_and_returns_depth_map(self) -> None:
        with (
            patch(
                "graph.nodes._map_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes._map_dialogue.build_map_question_prompt", _FAKE_PROMPT),
        ):
            from graph.nodes._map_dialogue import MapTurnPlan, respond_map

            result = await respond_map(
                _make_state([HumanMessage(content="hi")], turn_count=2),
                MapTurnPlan(depth_map=_DEPTH_MAP),
            )

        assert result["turn_count"] == 3
        assert result["depth_map"] == _DEPTH_MAP
        assert result["should_generate_note"] is False

    async def test_persists_the_resolved_aspect_name_in_turn_analysis(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[], has_misconception=False, response_mode="deepen", selected_aspect_id=_ASPECT_ID
        )
        with (
            patch(
                "graph.nodes._map_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes._map_dialogue.build_map_question_prompt", _FAKE_PROMPT),
        ):
            from graph.nodes._map_dialogue import MapTurnPlan, respond_map

            result = await respond_map(
                _make_state([HumanMessage(content="hi")]),
                MapTurnPlan(depth_map=_DEPTH_MAP, analysis=analysis),
            )

        assert result["turn_analysis"]["selected_aspect"] == "システムコールの定義"
        assert result["turn_analysis"]["selected_aspect_id"] == _ASPECT_ID
