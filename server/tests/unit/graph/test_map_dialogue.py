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

_NAMED_ASPECT_NAME = "TCP 3-way ハンドシェイク"
_NAMED_MAP = build_depth_map(
    "TCP",
    [
        DepthMapAspectDraft(
            name=_NAMED_ASPECT_NAME,
            is_core=True,
            defined_question="定義できるか",
            reasoned_question="なぜ必要か",
            applied_question="どう活かすか",
        )
    ],
)
_NAMED_ASPECT_ID = _NAMED_MAP["aspects"][0]["id"]


def _analysis_selecting(
    selected: str, observations: list[MapAspectObservation] | None = None
) -> MapDialogueTurnAnalysis:
    return MapDialogueTurnAnalysis(
        observations=observations or [],
        has_misconception=False,
        response_mode="deepen",
        selected_aspect_id=selected,
    )


async def _prepare_with(analysis: MapDialogueTurnAnalysis) -> Any:
    with patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", AsyncMock(return_value=analysis)):
        from graph.nodes._map_dialogue import prepare_map_turn

        return await prepare_map_turn(_make_state([HumanMessage(content="ハンドシェイクとは…")], depth_map=_NAMED_MAP))


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

    async def test_analysis_runs_for_a_dialogue_message_but_not_for_a_non_answer(self) -> None:
        from graph.nodes._map_dialogue import prepare_map_turn

        mock_analyze = AsyncMock(return_value=None)
        with patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", mock_analyze):
            await prepare_map_turn(
                _make_state([HumanMessage(content="システムコールとはカーネルに処理を頼む方法です")])
            )
            mock_analyze.assert_awaited_once()

            mock_analyze.reset_mock()
            await prepare_map_turn(_make_state([HumanMessage(content="わかりません")]))
            mock_analyze.assert_not_awaited()

    async def test_an_observation_for_an_unknown_aspect_grows_the_map(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[MapAspectObservation(aspect_id="割り込み", reached_stage="defined")],
            has_misconception=False,
            response_mode="expand",
            selected_aspect_id="割り込み",
        )
        with patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", AsyncMock(return_value=analysis)):
            from graph.nodes._map_dialogue import prepare_map_turn

            plan = await prepare_map_turn(_make_state([HumanMessage(content="割り込みも関係します")]))

        assert len(plan.depth_map["aspects"]) == len(_DEPTH_MAP["aspects"]) + 1
        new_aspect = plan.depth_map["aspects"][-1]
        assert new_aspect["name"] == "割り込み"
        assert new_aspect["is_core"] is False
        assert {"aspect_id": new_aspect["id"], "reached_stage": "defined"} in plan.map_covered

    async def test_a_selected_aspect_given_by_name_is_resolved_to_its_id(self) -> None:
        analysis = _analysis_selecting(_NAMED_ASPECT_NAME)
        plan = await _prepare_with(analysis)

        assert plan.analysis is not None
        assert plan.analysis.selected_aspect_id == _NAMED_ASPECT_ID
        assert plan.depth_map == _NAMED_MAP

    async def test_a_new_aspect_selected_and_observed_by_name_is_added_once_and_selected_by_id(self) -> None:
        analysis = _analysis_selecting(
            "TCP Slow Start", observations=[MapAspectObservation(aspect_id="TCP Slow Start", reached_stage="defined")]
        )
        plan = await _prepare_with(analysis)

        assert plan.analysis is not None
        assert [a["name"] for a in plan.depth_map["aspects"]].count("TCP Slow Start") == 1
        added = plan.depth_map["aspects"][-1]
        assert added["id"] == "tcp-slow-start"
        assert plan.analysis.selected_aspect_id == added["id"]

    async def test_a_new_aspect_only_selected_is_added_and_selected_by_id(self) -> None:
        plan = await _prepare_with(_analysis_selecting("TCP Slow Start"))

        assert plan.analysis is not None
        assert plan.analysis.selected_aspect_id == "tcp-slow-start"
        assert plan.depth_map["aspects"][-1]["name"] == "TCP Slow Start"

    async def test_a_selected_id_is_left_unchanged(self) -> None:
        plan = await _prepare_with(_analysis_selecting(_NAMED_ASPECT_ID))

        assert plan.analysis is not None
        assert plan.analysis.selected_aspect_id == _NAMED_ASPECT_ID
        assert plan.depth_map == _NAMED_MAP

    async def test_an_empty_selected_aspect_does_not_grow_the_map(self) -> None:
        plan = await _prepare_with(_analysis_selecting("  "))

        assert plan.depth_map == _NAMED_MAP

    async def test_the_persisted_record_carries_the_resolved_id(self) -> None:
        analysis = _analysis_selecting(_NAMED_ASPECT_NAME)
        with (
            patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", AsyncMock(return_value=analysis)),
            patch(
                "graph.nodes._map_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes._map_dialogue.build_map_question_prompt", _FAKE_PROMPT),
        ):
            from graph.nodes._map_dialogue import prepare_map_turn, respond_map

            state = _make_state([HumanMessage(content="ハンドシェイクとは…")], depth_map=_NAMED_MAP)
            result = await respond_map(state, await prepare_map_turn(state))

        record = result["turn_analysis"]
        assert record is not None and record["selected_aspect_id"] == _NAMED_ASPECT_ID

    async def test_wrap_up_is_suppressed_by_a_misconception(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[MapAspectObservation(aspect_id=_ASPECT_ID, reached_stage="reasoned")],
            has_misconception=True,
            error_summary="誤り",
            response_mode="reinforce",
            selected_aspect_id=_ASPECT_ID,
        )
        with patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", AsyncMock(return_value=analysis)):
            from graph.nodes._map_dialogue import prepare_map_turn

            plan = await prepare_map_turn(_make_state([HumanMessage(content="なぜカーネル経由か説明できます")]))

        assert plan.wrap_up is False

    async def test_wrap_up_is_not_offered_twice(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[MapAspectObservation(aspect_id=_ASPECT_ID, reached_stage="reasoned")],
            has_misconception=False,
            response_mode="expand",
            selected_aspect_id=_ASPECT_ID,
        )
        with patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", AsyncMock(return_value=analysis)):
            from graph.nodes._map_dialogue import prepare_map_turn

            plan = await prepare_map_turn(
                _make_state([HumanMessage(content="なぜカーネル経由か説明できます")], wrap_up_offered=True)
            )

        assert plan.wrap_up is False


class TestIntakeMessagesAreExcludedFromIntent:
    _MESSAGES = [
        HumanMessage(content="よくわからないです"),
        AIMessage(content="では最初の質問です"),
        HumanMessage(content="わかりません"),
    ]

    async def test_respond_map_classifies_only_post_intake_messages(self) -> None:
        mock_build = MagicMock(return_value=("QUESTION_PROMPT", "unknown_a"))
        with (
            patch(
                "graph.nodes._map_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="大丈夫ですよ"))),
            ),
            patch("graph.nodes._map_dialogue.build_map_question_prompt", mock_build),
        ):
            from graph.nodes._map_dialogue import MapTurnPlan, respond_map

            await respond_map(
                _make_state(list(self._MESSAGES), intake_message_count=1), MapTurnPlan(depth_map=_DEPTH_MAP)
            )

        assert len(mock_build.call_args.kwargs["messages"]) == 2

    async def test_respond_map_without_the_key_uses_the_full_history(self) -> None:
        mock_build = MagicMock(return_value=("QUESTION_PROMPT", "unknown_c"))
        with (
            patch(
                "graph.nodes._map_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="大丈夫ですよ"))),
            ),
            patch("graph.nodes._map_dialogue.build_map_question_prompt", mock_build),
        ):
            from graph.nodes._map_dialogue import MapTurnPlan, respond_map

            await respond_map(_make_state(list(self._MESSAGES)), MapTurnPlan(depth_map=_DEPTH_MAP))

        assert len(mock_build.call_args.kwargs["messages"]) == 3

    async def test_prepare_map_turn_ignores_intake_answers_for_intent(self) -> None:
        from graph.nodes._map_dialogue import prepare_map_turn

        mock_analyze = AsyncMock(return_value=None)
        with patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", mock_analyze):
            await prepare_map_turn(_make_state(list(self._MESSAGES), intake_message_count=1))
            mock_analyze.assert_not_awaited()

            await prepare_map_turn(_make_state([HumanMessage(content="よくわからないです")], intake_message_count=1))
            mock_analyze.assert_awaited_once()

    async def test_real_intent_is_unknown_b_not_unknown_c_with_the_key(self) -> None:
        from graph.prompts.question import classify_user_intent

        sliced = self._MESSAGES[1:]
        assert classify_user_intent(sliced) != "unknown_c"
        assert classify_user_intent(self._MESSAGES) == "unknown_c"


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

    async def test_tags_the_generation_with_the_map_prompt_fingerprint(self) -> None:
        fake_llm = MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です")))
        with (
            patch("graph.nodes._map_dialogue.llm", fake_llm),
            patch("graph.nodes._map_dialogue.build_map_question_prompt", _FAKE_PROMPT),
        ):
            from graph.nodes._map_dialogue import MapTurnPlan, respond_map
            from graph.prompts.map_question import MAP_PROMPT_FINGERPRINT

            await respond_map(_make_state([HumanMessage(content="hi")]), MapTurnPlan(depth_map=_DEPTH_MAP))

        metadata = fake_llm.ainvoke.call_args.kwargs["config"]["metadata"]
        assert metadata["prompt_fingerprint"] == MAP_PROMPT_FINGERPRINT

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

    async def test_without_analysis_turn_analysis_is_explicitly_none_and_wrap_up_not_offered(self) -> None:
        with (
            patch(
                "graph.nodes._map_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes._map_dialogue.build_map_question_prompt", _FAKE_PROMPT),
        ):
            from graph.nodes._map_dialogue import MapTurnPlan, respond_map

            result = await respond_map(_make_state([HumanMessage(content="hi")]), MapTurnPlan(depth_map=_DEPTH_MAP))

        assert "turn_analysis" in result
        assert result["turn_analysis"] is None
        assert result["wrap_up_offered"] is False

    async def test_wrap_up_offered_is_sticky_and_set_by_a_wrap_up_plan(self) -> None:
        with (
            patch(
                "graph.nodes._map_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes._map_dialogue.build_map_question_prompt", _FAKE_PROMPT),
        ):
            from graph.nodes._map_dialogue import MapTurnPlan, respond_map

            sticky = await respond_map(
                _make_state([HumanMessage(content="hi")], wrap_up_offered=True),
                MapTurnPlan(depth_map=_DEPTH_MAP, wrap_up=False),
            )
            fresh = await respond_map(
                _make_state([HumanMessage(content="hi")]), MapTurnPlan(depth_map=_DEPTH_MAP, wrap_up=True)
            )

        assert sticky["wrap_up_offered"] is True
        assert fresh["wrap_up_offered"] is True

    async def test_passes_the_plan_to_the_map_question_prompt(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[], has_misconception=False, response_mode="deepen", selected_aspect_id=_ASPECT_ID
        )
        covered: list[MapAspectProgress] = [{"aspect_id": _ASPECT_ID, "reached_stage": "defined"}]
        mock_build = MagicMock(return_value=("QUESTION_PROMPT", "dialogue"))
        with (
            patch(
                "graph.nodes._map_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes._map_dialogue.build_map_question_prompt", mock_build),
        ):
            from graph.nodes._map_dialogue import MapTurnPlan, respond_map

            await respond_map(
                _make_state([HumanMessage(content="hi")]),
                MapTurnPlan(depth_map=_DEPTH_MAP, map_covered=covered, analysis=analysis, wrap_up=True),
            )

        kwargs = mock_build.call_args.kwargs
        assert kwargs["depth_map"] == _DEPTH_MAP
        assert kwargs["map_covered"] == covered
        assert kwargs["turn_analysis"] is analysis
        assert kwargs["wrap_up"] is True
