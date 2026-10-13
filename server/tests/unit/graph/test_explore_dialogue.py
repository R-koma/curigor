from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from graph.output_schemas import ExploreTermDraft, ExploreTurnAnalysis
from graph.state import DepthMapAspectState, DepthMapState, LearningState


def _aspect(aspect_id: str, *, is_core: bool) -> DepthMapAspectState:
    return {
        "id": aspect_id,
        "name": aspect_id,
        "is_core": is_core,
        "defined_question": "d",
        "reasoned_question": "r",
        "applied_question": "a",
    }


MAP: DepthMapState = {
    "topic": "二分探索",
    "aspects": [_aspect("比較", is_core=True), _aspect("計算量", is_core=True), _aspect("前提", is_core=False)],
}


def _state(last: str = "次へ", **overrides: Any) -> LearningState:
    base: dict[str, Any] = {
        "user_id": "user-1",
        "messages": [HumanMessage("二分探索"), AIMessage("全体像"), HumanMessage(last)],
        "topic": "二分探索",
        "turn_count": 2,
        "should_generate_note": False,
        "session_type": "explore",
        "depth_map": MAP,
        "explore_overview": {},
        "explained_aspects": [],
        "explore_terms": [],
        "explore_questions": [],
        "wrap_up_offered": False,
        "end_confirmation": None,
        "learning_source": "",
    }
    base.update(overrides)
    return cast(LearningState, base)


async def _plan(state: LearningState, analysis: ExploreTurnAnalysis | None) -> Any:
    with patch("graph.nodes._explore_dialogue.analyze_explore_turn", new=AsyncMock(return_value=analysis)):
        from graph.nodes._explore_dialogue import prepare_explore_turn

        return await prepare_explore_turn(state)


class TestPrepareExploreTurn:
    async def test_next_explains_the_first_unexplained_core_aspect(self) -> None:
        plan = await _plan(_state(), ExploreTurnAnalysis(user_intent="next"))

        assert plan.aspect_id == "比較"
        assert plan.explained_aspects == ["比較"]
        assert plan.wrap_up is False
        assert plan.end_confirmation is None

    async def test_choose_aspect_uses_the_chosen_one(self) -> None:
        plan = await _plan(_state("計算量から"), ExploreTurnAnalysis(user_intent="choose_aspect", aspect_id="計算量"))

        assert plan.aspect_id == "計算量"
        assert plan.explained_aspects == ["計算量"]

    async def test_free_question_outside_the_map_adds_no_aspect(self) -> None:
        plan = await _plan(
            _state("ハッシュ表との違いは？"),
            ExploreTurnAnalysis(user_intent="question", aspect_id="ハッシュ表", question_summary="ハッシュ表との違い"),
        )

        assert plan.aspect_id is None
        assert plan.explained_aspects == []
        assert plan.question_summary == "ハッシュ表との違い"
        assert len(MAP["aspects"]) == 3

    async def test_failed_analysis_answers_as_a_question(self) -> None:
        plan = await _plan(_state(), None)

        assert plan.user_intent == "question"
        assert plan.terms == []

    async def test_wraps_up_once_every_core_aspect_is_explained(self) -> None:
        plan = await _plan(_state(explained_aspects=["比較"]), ExploreTurnAnalysis(user_intent="next"))

        assert plan.wrap_up is True
        assert plan.end_confirmation == "offered"

    async def test_does_not_wrap_up_twice(self) -> None:
        state = _state(explained_aspects=["比較", "計算量"], wrap_up_offered=True)

        plan = await _plan(state, ExploreTurnAnalysis(user_intent="next"))

        assert plan.wrap_up is False
        assert plan.end_confirmation is None

    async def test_second_wish_to_end_confirms(self) -> None:
        state = _state("終わります", end_confirmation="offered")

        plan = await _plan(state, ExploreTurnAnalysis(user_intent="end_session"))

        assert plan.end_confirmation == "confirmed"


def _llm(content: str = "説明です", message_id: str | None = "ai-1") -> MagicMock:
    mock = MagicMock()
    mock.ainvoke = AsyncMock(return_value=AIMessage(content=content, id=message_id))
    return mock


async def _respond(state: LearningState, plan: Any, mock_llm: MagicMock) -> dict[str, Any]:
    with (
        patch("graph.nodes._explore_dialogue.llm", mock_llm),
        patch("graph.nodes._explore_dialogue.load_image_blocks", new=AsyncMock(return_value=[])),
    ):
        from graph.nodes._explore_dialogue import respond_explore

        return await respond_explore(state, plan)


class TestRespondExplore:
    async def test_explains_and_records_the_turn(self) -> None:
        state = _state()
        plan = await _plan(
            state,
            ExploreTurnAnalysis(
                user_intent="next", terms=[ExploreTermDraft(term="計算量", reading="けいさんりょう", meaning="手間")]
            ),
        )
        mock_llm = _llm()

        result = await _respond(state, plan, mock_llm)

        prompt = mock_llm.ainvoke.call_args.args[0][0].content
        assert "1回の応答で説明する概念は1つ" in prompt
        assert result["messages"][0].content == "説明です"
        assert result["explained_aspects"] == ["比較"]
        assert result["explore_terms"] == [{"term": "計算量", "reading": "けいさんりょう", "meaning": "手間"}]
        assert result["explore_turn"] == {"user_intent": "next", "aspect_id": "比較", "wrap_up": False}
        assert result["end_confirmation"] is None
        assert result["should_generate_note"] is False
        assert result["turn_count"] == 3
        assert mock_llm.ainvoke.call_args.kwargs["task"] == "explore-dialogue"

    async def test_next_after_every_aspect_is_explained_uses_the_all_covered_section(self) -> None:
        state = _state(explained_aspects=["比較", "計算量", "前提"])
        plan = await _plan(state, ExploreTurnAnalysis(user_intent="next"))
        mock_llm = _llm()

        await _respond(state, plan, mock_llm)

        prompt = mock_llm.ainvoke.call_args.args[0][0].content
        assert "ひととおり説明し終えました" in prompt
        assert "1回の応答で説明する概念は1つ" not in prompt

    async def test_question_is_recorded_with_the_answer_message_id(self) -> None:
        state = _state("なぜ並べるの？")
        plan = await _plan(state, ExploreTurnAnalysis(user_intent="question", question_summary="なぜ並べるのか"))

        result = await _respond(state, plan, _llm(message_id=None))

        answer = result["messages"][0]
        assert answer.id
        assert result["explore_questions"] == [{"question": "なぜ並べるのか", "answer_message_id": answer.id}]

    async def test_confirmed_turn_calls_no_llm_and_adds_no_message(self) -> None:
        state = _state("終わります", end_confirmation="offered")
        plan = await _plan(state, ExploreTurnAnalysis(user_intent="end_session"))
        mock_llm = _llm()

        result = await _respond(state, plan, mock_llm)

        mock_llm.ainvoke.assert_not_called()
        assert "messages" not in result
        assert result["end_confirmation"] == "confirmed"


class TestExploreDialogueRouter:
    async def test_runs_the_setup_turn_until_a_map_exists(self) -> None:
        setup = AsyncMock(return_value={"messages": []})
        with patch("graph.nodes.explore_dialogue.handle_explore_setup_turn", new=setup):
            from graph.nodes.explore_dialogue import explore_dialogue

            await explore_dialogue(_state(depth_map=None))

        setup.assert_awaited_once()
