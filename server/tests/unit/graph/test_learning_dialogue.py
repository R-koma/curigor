from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage

from graph.output_schemas import AspectObservation, DialogueTurnAnalysis
from graph.state import LearningState

SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
NOTE_ID = UUID("00000000-0000-0000-0000-000000000001")

_FAKE_PROMPT = MagicMock(return_value=("QUESTION_PROMPT", "dialogue"))
_NO_ANALYSIS = AsyncMock(return_value=None)


def _make_state(messages: list[Any], **overrides: object) -> LearningState:
    base: dict[str, object] = {
        "user_id": "user-abc",
        "dialogue_session_id": SESSION_ID,
        "note_id": NOTE_ID,
        "messages": messages,
        "topic": "二分探索",
        "turn_count": 2,
        "should_generate_note": False,
        "session_type": "learning",
    }
    base.update(overrides)
    return cast(LearningState, base)


class TestLearningDialogue:
    async def test_increments_turn_count(self) -> None:
        with (
            patch(
                "graph.nodes.learning_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes.learning_dialogue.build_question_prompt", _FAKE_PROMPT),
            patch("graph.nodes.learning_dialogue.analyze_dialogue_turn", _NO_ANALYSIS),
        ):
            from graph.nodes.learning_dialogue import learning_dialogue

            result = await learning_dialogue(_make_state([HumanMessage(content="hi")], turn_count=2))

        assert result["turn_count"] == 3

    async def test_should_generate_note_is_always_false(self) -> None:
        with (
            patch(
                "graph.nodes.learning_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes.learning_dialogue.build_question_prompt", _FAKE_PROMPT),
            patch("graph.nodes.learning_dialogue.analyze_dialogue_turn", _NO_ANALYSIS),
        ):
            from graph.nodes.learning_dialogue import learning_dialogue

            result = await learning_dialogue(_make_state([HumanMessage(content="hi")]))

        assert result["should_generate_note"] is False

    async def test_appends_response_message(self) -> None:
        response = AIMessage(content="次はどう考えますか？")
        with (
            patch("graph.nodes.learning_dialogue.llm", MagicMock(ainvoke=AsyncMock(return_value=response))),
            patch("graph.nodes.learning_dialogue.build_question_prompt", _FAKE_PROMPT),
            patch("graph.nodes.learning_dialogue.analyze_dialogue_turn", _NO_ANALYSIS),
        ):
            from graph.nodes.learning_dialogue import learning_dialogue

            result = await learning_dialogue(_make_state([HumanMessage(content="hi")]))

        assert result["messages"] == [response]

    async def test_passes_only_recent_six_messages_to_question_prompt(self) -> None:
        messages = [HumanMessage(content=f"m{i}") for i in range(8)]
        mock_build = MagicMock(return_value=("QUESTION_PROMPT", "dialogue"))
        with (
            patch(
                "graph.nodes.learning_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes.learning_dialogue.build_question_prompt", mock_build),
            patch("graph.nodes.learning_dialogue.analyze_dialogue_turn", _NO_ANALYSIS),
        ):
            from graph.nodes.learning_dialogue import learning_dialogue

            await learning_dialogue(_make_state(messages))

        recent = mock_build.call_args.kwargs["recent_messages"]
        assert "m2" in recent and "m7" in recent  # 直近6件は含む
        assert "m0" not in recent and "m1" not in recent  # それより前は含まない


class TestLearningDialogueCoverage:
    _ANALYSIS = DialogueTurnAnalysis(
        observations=[AspectObservation(aspect="計算量", reached_depth="defined")],
        has_misconception=False,
        response_mode="expand",
        selected_aspect="計算量",
    )

    async def test_merges_analysis_observations_into_covered_aspects(self) -> None:
        mock_build = MagicMock(return_value=("QUESTION_PROMPT", "dialogue"))
        state = _make_state(
            [HumanMessage(content="二分探索の計算量は O(log n) です")],
            covered_aspects=[{"aspect": "前提条件", "reached_depth": "exemplified"}],
        )
        with (
            patch(
                "graph.nodes.learning_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes.learning_dialogue.build_question_prompt", mock_build),
            patch("graph.nodes.learning_dialogue.analyze_dialogue_turn", AsyncMock(return_value=self._ANALYSIS)),
        ):
            from graph.nodes.learning_dialogue import learning_dialogue

            result = await learning_dialogue(state)

        assert result["covered_aspects"] == [
            {"aspect": "前提条件", "reached_depth": "exemplified"},
            {"aspect": "計算量", "reached_depth": "defined"},
        ]
        assert mock_build.call_args.kwargs["turn_analysis"] is self._ANALYSIS
        assert mock_build.call_args.kwargs["covered_aspects"] == result["covered_aspects"]

    async def test_missing_covered_aspects_in_state_does_not_crash(self) -> None:
        """旧チェックポイント（covered_aspects 欠損）からの再開でも落ちない。"""
        with (
            patch(
                "graph.nodes.learning_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes.learning_dialogue.build_question_prompt", _FAKE_PROMPT),
            patch("graph.nodes.learning_dialogue.analyze_dialogue_turn", _NO_ANALYSIS),
        ):
            from graph.nodes.learning_dialogue import learning_dialogue

            result = await learning_dialogue(_make_state([HumanMessage(content="hi")]))

        assert result["covered_aspects"] == []

    async def test_analysis_failure_falls_back_without_coverage_change(self) -> None:
        mock_build = MagicMock(return_value=("QUESTION_PROMPT", "dialogue"))
        existing = [{"aspect": "前提条件", "reached_depth": "defined"}]
        with (
            patch(
                "graph.nodes.learning_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes.learning_dialogue.build_question_prompt", mock_build),
            patch("graph.nodes.learning_dialogue.analyze_dialogue_turn", AsyncMock(return_value=None)),
        ):
            from graph.nodes.learning_dialogue import learning_dialogue

            result = await learning_dialogue(_make_state([HumanMessage(content="hi")], covered_aspects=list(existing)))

        assert result["covered_aspects"] == existing
        assert mock_build.call_args.kwargs["turn_analysis"] is None

    async def test_skips_analysis_for_non_dialogue_intent(self) -> None:
        mock_analyze = AsyncMock(return_value=None)
        with (
            patch(
                "graph.nodes.learning_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="大丈夫ですよ"))),
            ),
            patch("graph.nodes.learning_dialogue.build_question_prompt", _FAKE_PROMPT),
            patch("graph.nodes.learning_dialogue.analyze_dialogue_turn", mock_analyze),
        ):
            from graph.nodes.learning_dialogue import learning_dialogue

            await learning_dialogue(_make_state([HumanMessage(content="わかりません")]))

        mock_analyze.assert_not_awaited()


class TestLearningDialogueTurnAnalysisRecord:
    """事前分析の決定内容を state に残す（eval の regression 再現に必要）。"""

    _ANALYSIS = DialogueTurnAnalysis(
        observations=[AspectObservation(aspect="計算量", reached_depth="defined")],
        has_misconception=True,
        response_mode="reinforce",
        selected_aspect="計算量",
        error_summary="O(n) と混同している",
    )

    async def test_persists_decided_mode_and_aspect(self) -> None:
        with (
            patch(
                "graph.nodes.learning_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes.learning_dialogue.build_question_prompt", _FAKE_PROMPT),
            patch("graph.nodes.learning_dialogue.analyze_dialogue_turn", AsyncMock(return_value=self._ANALYSIS)),
        ):
            from graph.nodes.learning_dialogue import learning_dialogue

            result = await learning_dialogue(_make_state([HumanMessage(content="計算量は O(n) です")]))

        assert result["turn_analysis"] == {
            "response_mode": "reinforce",
            "selected_aspect": "計算量",
            "has_misconception": True,
            "error_summary": "O(n) と混同している",
            "wrap_up": False,
        }

    async def test_observations_are_not_duplicated_into_the_record(self) -> None:
        """observations は covered_aspects 側に持つので record には含めない。"""
        with (
            patch(
                "graph.nodes.learning_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes.learning_dialogue.build_question_prompt", _FAKE_PROMPT),
            patch("graph.nodes.learning_dialogue.analyze_dialogue_turn", AsyncMock(return_value=self._ANALYSIS)),
        ):
            from graph.nodes.learning_dialogue import learning_dialogue

            result = await learning_dialogue(_make_state([HumanMessage(content="計算量は O(n) です")]))

        assert "observations" not in result["turn_analysis"]

    async def test_writes_none_when_analysis_did_not_run(self) -> None:
        """前ターンの決定内容が残ると、チェックポイント履歴を辿る側が取り違えるため。"""
        stale: dict[str, object] = {
            "response_mode": "expand",
            "selected_aspect": "前提条件",
            "error_summary": "",
        }
        with (
            patch(
                "graph.nodes.learning_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="大丈夫ですよ"))),
            ),
            patch("graph.nodes.learning_dialogue.build_question_prompt", _FAKE_PROMPT),
            patch("graph.nodes.learning_dialogue.analyze_dialogue_turn", _NO_ANALYSIS),
        ):
            from graph.nodes.learning_dialogue import learning_dialogue

            result = await learning_dialogue(_make_state([HumanMessage(content="わかりません")], turn_analysis=stale))

        assert result["turn_analysis"] is None


class TestLearningDialogueWrapUp:
    _TWO_REACHED = [
        {"aspect": "前提条件", "reached_depth": "exemplified"},
        {"aspect": "計算量", "reached_depth": "applied"},
    ]

    def _analysis(self, *, has_misconception: bool = False) -> DialogueTurnAnalysis:
        return DialogueTurnAnalysis(
            observations=[AspectObservation(aspect="境界条件", reached_depth="exemplified")],
            has_misconception=has_misconception,
            error_summary="範囲の端の扱いを取り違えている" if has_misconception else "",
            response_mode="reinforce" if has_misconception else "expand",
            selected_aspect="境界条件",
        )

    async def _run(
        self, state: LearningState, analysis: DialogueTurnAnalysis | None
    ) -> tuple[dict[str, Any], MagicMock]:
        mock_build = MagicMock(return_value=("QUESTION_PROMPT", "dialogue"))
        with (
            patch(
                "graph.nodes.learning_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="応答です"))),
            ),
            patch("graph.nodes.learning_dialogue.build_question_prompt", mock_build),
            patch("graph.nodes.learning_dialogue.analyze_dialogue_turn", AsyncMock(return_value=analysis)),
        ):
            from graph.nodes.learning_dialogue import learning_dialogue

            result = await learning_dialogue(state)
        return result, mock_build

    def _state(self, **overrides: object) -> LearningState:
        fields: dict[str, object] = {"covered_aspects": self._TWO_REACHED, **overrides}
        return _make_state([HumanMessage(content="範囲の端は left <= right の間だけ探索します")], **fields)

    async def test_offers_wrap_up_when_the_third_aspect_reaches_the_target(self) -> None:
        result, build = await self._run(self._state(), self._analysis())

        assert build.call_args.kwargs["wrap_up"] is True
        assert result["wrap_up_offered"] is True
        assert result["turn_analysis"]["wrap_up"] is True

    async def test_does_not_offer_below_the_threshold(self) -> None:
        state = self._state(covered_aspects=self._TWO_REACHED[:1])

        result, build = await self._run(state, self._analysis())

        assert build.call_args.kwargs["wrap_up"] is False
        assert result["wrap_up_offered"] is False
        assert result["turn_analysis"]["wrap_up"] is False

    async def test_misconception_takes_priority_over_wrap_up(self) -> None:
        result, build = await self._run(self._state(), self._analysis(has_misconception=True))

        assert build.call_args.kwargs["wrap_up"] is False
        assert result["wrap_up_offered"] is False

    async def test_offers_only_once_per_session(self) -> None:
        result, build = await self._run(self._state(wrap_up_offered=True), self._analysis())

        assert build.call_args.kwargs["wrap_up"] is False
        assert result["wrap_up_offered"] is True

    async def test_analysis_failure_does_not_offer(self) -> None:
        three_reached = [*self._TWO_REACHED, {"aspect": "境界条件", "reached_depth": "exemplified"}]

        result, build = await self._run(self._state(covered_aspects=three_reached), None)

        assert build.call_args.kwargs["wrap_up"] is False
        assert result["wrap_up_offered"] is False
        assert result["turn_analysis"] is None

    async def test_focus_aspects_require_every_listed_aspect(self) -> None:
        state = self._state(focus_aspects=["前提条件", "計算量", "境界条件", "用途"])

        result, build = await self._run(state, self._analysis())

        assert build.call_args.kwargs["wrap_up"] is False
