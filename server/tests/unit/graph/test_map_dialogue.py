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

    async def test_analysis_runs_for_every_message_including_a_non_answer(self) -> None:
        from graph.nodes._map_dialogue import prepare_map_turn

        mock_analyze = AsyncMock(return_value=None)
        with patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", mock_analyze):
            await prepare_map_turn(
                _make_state([HumanMessage(content="システムコールとはカーネルに処理を頼む方法です")])
            )
            await prepare_map_turn(_make_state([HumanMessage(content="わかりません")]))

        assert mock_analyze.await_count == 2

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


_LINUX_MAP = build_depth_map(
    "Linuxの仕組み",
    [
        DepthMapAspectDraft(
            name="カーネルの役割",
            is_core=True,
            defined_question="カーネルを定義できるか",
            reasoned_question="なぜ必要か",
            applied_question="どう活かすか",
        )
    ],
)
_CORRECTION_TEXT = "この仕組みって言ったけど間違えた。Linuxの仕組み、これに変更して"
_COVERED: list[MapAspectProgress] = [{"aspect_id": _ASPECT_ID, "reached_stage": "reasoned"}]
_PENDING: dict[str, object] = {"pending_topic_correction": {"new_topic": "Linuxの仕組み"}}


def _correction_analysis(corrected_topic: str = "Linuxの仕組み") -> MapDialogueTurnAnalysis:
    return MapDialogueTurnAnalysis(
        corrected_topic=corrected_topic,
        observations=[MapAspectObservation(aspect_id="仕組みの対象変更", reached_stage="mentioned")],
        has_misconception=False,
        response_mode="expand",
        selected_aspect_id="仕組みの対象変更",
    )


def _answer_message(answer: str) -> HumanMessage:
    return HumanMessage(content="はい", additional_kwargs={"topic_correction_answer": answer})


async def _prepare(
    messages: list[Any], analysis: MapDialogueTurnAnalysis | None, new_map: Any, **overrides: object
) -> tuple[Any, AsyncMock]:
    generate = AsyncMock(return_value=new_map)
    with (
        patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", AsyncMock(return_value=analysis)),
        patch("graph.nodes._map_dialogue.generate_depth_map", generate),
    ):
        from graph.nodes._map_dialogue import prepare_map_turn

        state = _make_state(
            messages,
            topic="この仕組み",
            learning_goal="OS の全体像",
            learning_source="教科書",
            prior_knowledge="少し",
            map_covered=list(_COVERED),
            **overrides,
        )
        return await prepare_map_turn(state), generate


async def _respond(plan: Any, state: LearningState, build_prompt: MagicMock = _FAKE_PROMPT) -> dict[str, Any]:
    with (
        patch(
            "graph.nodes._map_dialogue.llm",
            MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="応答です"))),
        ),
        patch("graph.nodes._map_dialogue.build_map_question_prompt", build_prompt),
        patch("graph.nodes._map_dialogue.load_image_blocks", AsyncMock(return_value=[])),
    ):
        from graph.nodes._map_dialogue import respond_map

        return await respond_map(state, plan)


class TestTopicCorrectionAsked:
    async def test_a_correction_is_asked_not_applied(self) -> None:
        plan, generate = await _prepare([HumanMessage(content=_CORRECTION_TEXT)], _correction_analysis(), _LINUX_MAP)

        generate.assert_not_awaited()
        assert plan.depth_map == _DEPTH_MAP
        assert plan.map_covered == _COVERED
        assert plan.topic_correction == {
            "previous_topic": "この仕組み",
            "new_topic": "Linuxの仕組み",
            "status": "asked",
        }
        assert plan.analysis is None

    async def test_the_same_topic_is_an_ordinary_turn(self) -> None:
        plan, _ = await _prepare([HumanMessage(content="…")], _correction_analysis(" この仕組み "), _LINUX_MAP)

        assert plan.topic_correction is None

    async def test_a_long_topic_is_truncated(self) -> None:
        plan, _ = await _prepare([HumanMessage(content="…")], _correction_analysis("あ" * 100), _LINUX_MAP)

        assert plan.topic_correction is not None
        assert plan.topic_correction["new_topic"] == "あ" * 60

    async def test_respond_map_asks_without_calling_the_llm(self) -> None:
        plan, _ = await _prepare([HumanMessage(content=_CORRECTION_TEXT)], _correction_analysis(), _LINUX_MAP)
        llm = MagicMock(ainvoke=AsyncMock())
        with patch("graph.nodes._map_dialogue.llm", llm):
            from graph.nodes._map_dialogue import respond_map

            result = await respond_map(_make_state([HumanMessage(content=_CORRECTION_TEXT)], topic="この仕組み"), plan)

        llm.ainvoke.assert_not_awaited()
        message = result["messages"][0]
        assert "「この仕組み」から「Linuxの仕組み」" in message.content
        assert message.additional_kwargs["topic_correction_card"] == {
            "previous_topic": "この仕組み",
            "new_topic": "Linuxの仕組み",
        }
        assert result["pending_topic_correction"] == {"new_topic": "Linuxの仕組み"}
        assert "topic" not in result
        assert result["turn_analysis"]["topic_correction"]["status"] == "asked"
        assert result["turn_analysis"]["selected_aspect"] == ""
        assert result["turn_analysis"]["selected_aspect_id"] == ""
        assert result["wrap_up_offered"] is False


class TestTopicCorrectionAnswered:
    async def test_accept_rebuilds_the_map_with_the_learning_plan_carried_over(self) -> None:
        plan, generate = await _prepare([_answer_message("accept")], None, _LINUX_MAP, **_PENDING)

        generate.assert_awaited_once_with(
            topic="Linuxの仕組み", purpose="OS の全体像", source="教科書", prior_knowledge="少し"
        )
        assert plan.depth_map == _LINUX_MAP
        assert plan.map_covered == []
        assert plan.topic_correction == {
            "previous_topic": "この仕組み",
            "new_topic": "Linuxの仕組み",
            "status": "accepted",
        }
        assert plan.analysis is not None
        assert plan.analysis.selected_aspect_id == _LINUX_MAP["aspects"][0]["id"]

    async def test_accept_does_not_run_the_turn_analysis(self) -> None:
        analyze = AsyncMock()
        with (
            patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", analyze),
            patch("graph.nodes._map_dialogue.generate_depth_map", AsyncMock(return_value=_LINUX_MAP)),
        ):
            from graph.nodes._map_dialogue import prepare_map_turn

            await prepare_map_turn(_make_state([_answer_message("accept")], topic="この仕組み", **_PENDING))

        analyze.assert_not_awaited()

    async def test_accept_with_a_failed_generation_keeps_the_topic_and_map(self) -> None:
        plan, _ = await _prepare([_answer_message("accept")], None, None, **_PENDING)

        assert plan.depth_map == _DEPTH_MAP
        assert plan.map_covered == _COVERED
        assert plan.topic_correction is not None
        assert plan.topic_correction["status"] == "failed"

    async def test_decline_changes_nothing(self) -> None:
        plan, generate = await _prepare([_answer_message("decline")], None, _LINUX_MAP, **_PENDING)

        generate.assert_not_awaited()
        assert plan.depth_map == _DEPTH_MAP
        assert plan.map_covered == _COVERED
        assert plan.topic_correction is not None
        assert plan.topic_correction["status"] == "declined"

    async def test_free_text_while_pending_drops_the_pending_and_runs_the_ordinary_turn(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[MapAspectObservation(aspect_id=_ASPECT_ID, reached_stage="defined")],
            has_misconception=False,
            response_mode="deepen",
            selected_aspect_id=_ASPECT_ID,
        )
        messages = [HumanMessage(content="システムコールはカーネルへの依頼です")]
        plan, generate = await _prepare(messages, analysis, _LINUX_MAP, **_PENDING)

        generate.assert_not_awaited()
        assert plan.topic_correction is None
        assert plan.analysis is not None
        result = await _respond(plan, _make_state(messages, topic="この仕組み", **_PENDING))
        assert result["pending_topic_correction"] is None

    async def test_an_answer_without_a_pending_is_ignored(self) -> None:
        plan, generate = await _prepare([_answer_message("accept")], _correction_analysis(""), _LINUX_MAP)

        generate.assert_not_awaited()
        assert plan.topic_correction is None

    async def test_respond_map_applies_an_accepted_correction(self) -> None:
        plan, _ = await _prepare([_answer_message("accept")], None, _LINUX_MAP, **_PENDING)
        build_prompt = MagicMock(return_value=("QUESTION_PROMPT", "dialogue"))

        result = await _respond(
            plan,
            _make_state([_answer_message("accept")], topic="この仕組み", wrap_up_offered=True, **_PENDING),
            build_prompt,
        )

        assert build_prompt.call_args.kwargs["topic"] == "Linuxの仕組み"
        assert build_prompt.call_args.kwargs["topic_correction"] == plan.topic_correction
        assert result["topic"] == "Linuxの仕組み"
        assert result["depth_map"] == _LINUX_MAP
        assert result["map_covered"] == []
        assert result["wrap_up_offered"] is False
        assert result["pending_topic_correction"] is None
        assert result["turn_analysis"]["topic_correction"]["status"] == "accepted"

    async def test_respond_map_leaves_the_topic_alone_when_declined(self) -> None:
        plan, _ = await _prepare([_answer_message("decline")], None, _LINUX_MAP, **_PENDING)

        result = await _respond(plan, _make_state([_answer_message("decline")], topic="この仕組み", **_PENDING))

        assert "topic" not in result
        assert result["pending_topic_correction"] is None
        assert result["map_covered"] == _COVERED


def _intent_analysis(user_intent: str) -> MapDialogueTurnAnalysis:
    return MapDialogueTurnAnalysis.model_validate(
        {
            "user_intent": user_intent,
            "observations": [],
            "has_misconception": False,
            "response_mode": "deepen",
            "selected_aspect_id": _ASPECT_ID,
        }
    )


async def _prepare_intent(user_intent: str, earlier: list[Any] | None = None, **state: object) -> Any:
    with patch(
        "graph.nodes._map_dialogue.analyze_map_dialogue_turn", AsyncMock(return_value=_intent_analysis(user_intent))
    ):
        from graph.nodes._map_dialogue import prepare_map_turn

        return await prepare_map_turn(_make_state([*(earlier or []), HumanMessage(content="発話")], **state))


class TestUnknownStreak:
    async def test_a_first_dont_know_counts_one(self) -> None:
        plan = await _prepare_intent("dont_know")

        assert plan.unknown_streak == 1

    async def test_consecutive_dont_knows_count_up(self) -> None:
        previous = {
            "response_mode": "deepen",
            "selected_aspect": "x",
            "has_misconception": False,
            "error_summary": "",
            "user_intent": "dont_know",
            "unknown_streak": 2,
        }

        plan = await _prepare_intent("dont_know", turn_analysis=previous)

        assert plan.unknown_streak == 3

    async def test_a_dont_know_after_an_explanation_starts_over(self) -> None:
        previous = {"response_mode": "deepen", "selected_aspect": "x", "has_misconception": False, "error_summary": ""}

        plan = await _prepare_intent("dont_know", turn_analysis=previous)

        assert plan.unknown_streak == 1

    async def test_an_empty_previous_record_counts_the_earlier_dont_knows_by_keyword(self) -> None:
        earlier = [
            HumanMessage(content="プロセスはプログラムの実行単位です"),
            AIMessage(content="問い1"),
            HumanMessage(content="わかりません"),
            AIMessage(content="問い2"),
            HumanMessage(content="わからないです"),
            AIMessage(content="問い3"),
        ]

        plan = await _prepare_intent("dont_know", earlier, turn_analysis=None)

        assert plan.unknown_streak == 3

    async def test_an_empty_previous_record_after_an_explanation_counts_one(self) -> None:
        earlier = [HumanMessage(content="プロセスはプログラムの実行単位です"), AIMessage(content="問い")]

        plan = await _prepare_intent("dont_know", earlier, turn_analysis=None)

        assert plan.unknown_streak == 1

    async def test_a_partial_dont_know_is_not_counted(self) -> None:
        previous = {
            "response_mode": "deepen",
            "selected_aspect": "x",
            "has_misconception": False,
            "error_summary": "",
            "user_intent": "dont_know",
            "unknown_streak": 1,
        }

        plan = await _prepare_intent("partial_dont_know", turn_analysis=previous)

        assert plan.unknown_streak == 0


class TestIntentInThePlan:
    async def test_wrap_up_is_not_offered_to_a_non_explanation(self) -> None:
        covered = [{"aspect_id": _ASPECT_ID, "reached_stage": "reasoned"}]

        explanation = await _prepare_intent("explanation", map_covered=covered)
        end_session = await _prepare_intent("end_session", map_covered=covered)

        assert explanation.wrap_up is True
        assert end_session.wrap_up is False

    async def test_the_record_keeps_a_non_default_intent_and_streak(self) -> None:
        from graph.nodes._map_dialogue import _to_record

        record = _to_record(await _prepare_intent("dont_know"))

        assert record is not None
        assert record["user_intent"] == "dont_know"
        assert record["unknown_streak"] == 1

    async def test_the_record_of_an_explanation_matches_the_earlier_shape(self) -> None:
        from graph.nodes._map_dialogue import _to_record

        record = _to_record(await _prepare_intent("explanation"))

        assert record is not None
        assert "user_intent" not in record
        assert "unknown_streak" not in record


def _end_analysis(**overrides: Any) -> MapDialogueTurnAnalysis:
    return MapDialogueTurnAnalysis(
        user_intent="end_session",
        observations=[],
        has_misconception=False,
        response_mode="deepen",
        selected_aspect_id=_ASPECT_ID,
        **overrides,
    )


async def _prepare_turn(analysis: MapDialogueTurnAnalysis | None, **state: object) -> Any:
    with patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", AsyncMock(return_value=analysis)):
        from graph.nodes._map_dialogue import prepare_map_turn

        return await prepare_map_turn(_make_state([HumanMessage(content="今日はここまでにします")], **state))


class TestEndConfirmation:
    async def test_first_wish_to_end_is_offered(self) -> None:
        plan = await _prepare_turn(_end_analysis())
        assert plan.end_confirmation == "offered"

    async def test_wish_to_end_after_an_offer_is_confirmed(self) -> None:
        plan = await _prepare_turn(_end_analysis(), end_confirmation="offered")
        assert plan.end_confirmation == "confirmed"

    async def test_an_explanation_after_an_offer_clears_it(self) -> None:
        plan = await _prepare_turn(_analysis_selecting(_ASPECT_ID), end_confirmation="offered")
        assert plan.end_confirmation is None

    async def test_wrap_up_is_an_offer(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[MapAspectObservation(aspect_id=_ASPECT_ID, reached_stage="reasoned")],
            has_misconception=False,
            response_mode="expand",
            selected_aspect_id=_ASPECT_ID,
        )
        plan = await _prepare_turn(analysis)
        assert plan.wrap_up is True
        assert plan.end_confirmation == "offered"

    async def test_analysis_failure_clears_the_offer(self) -> None:
        plan = await _prepare_turn(None, end_confirmation="offered")
        assert plan.end_confirmation is None

    async def test_confirmed_turn_skips_the_llm_and_adds_no_message(self) -> None:
        from graph.nodes._map_dialogue import MapTurnPlan, respond_map

        mock_llm = MagicMock(ainvoke=AsyncMock())
        plan = MapTurnPlan(depth_map=_DEPTH_MAP, analysis=_end_analysis(), end_confirmation="confirmed")
        with patch("graph.nodes._map_dialogue.llm", mock_llm):
            result = await respond_map(_make_state([HumanMessage(content="はい、終わります")]), plan)

        mock_llm.ainvoke.assert_not_called()
        assert "messages" not in result
        assert result["end_confirmation"] == "confirmed"
        assert result["should_generate_note"] is False
        assert result["turn_count"] == 3

    async def test_ordinary_turn_writes_none_explicitly(self) -> None:
        from graph.nodes._map_dialogue import MapTurnPlan, respond_map

        plan = MapTurnPlan(depth_map=_DEPTH_MAP, analysis=_analysis_selecting(_ASPECT_ID))
        with (
            patch(
                "graph.nodes._map_dialogue.llm", MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="問い")))
            ),
            patch("graph.nodes._map_dialogue.build_map_question_prompt", _FAKE_PROMPT),
        ):
            result = await respond_map(_make_state([HumanMessage(content="説明")], end_confirmation="offered"), plan)

        assert "end_confirmation" in result
        assert result["end_confirmation"] is None
