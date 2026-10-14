from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from graph.output_schemas import ExploreTermDraft, ExploreTurnAnalysis
from graph.state import LearningState


def _state(last: str = "二分探索って何？", **overrides: Any) -> LearningState:
    base: dict[str, Any] = {
        "user_id": "user-1",
        "messages": [HumanMessage("二分探索って何？"), AIMessage("説明"), HumanMessage(last)],
        "topic": "二分探索",
        "turn_count": 1,
        "should_generate_note": False,
        "session_type": "explore",
        "explore_terms": [],
        "explore_questions": [],
        "wrap_up_offered": False,
        "end_confirmation": None,
    }
    base.update(overrides)
    return cast(LearningState, base)


async def _plan(state: LearningState, analysis: ExploreTurnAnalysis | None) -> Any:
    with patch("graph.nodes._explore_dialogue.analyze_explore_turn", new=AsyncMock(return_value=analysis)):
        from graph.nodes._explore_dialogue import prepare_explore_turn

        return await prepare_explore_turn(state)


_ASKED = [{"question": "二分探索とは", "answer_message_id": "a1"}]


class TestPrepareExploreTurn:
    async def test_a_question_is_recorded_and_not_wrapped_up(self) -> None:
        plan = await _plan(_state(), ExploreTurnAnalysis(user_intent="question", question_summary="二分探索とは"))

        assert plan.user_intent == "question"
        assert plan.question_summary == "二分探索とは"
        assert plan.wrap_up is False
        assert plan.end_confirmation is None

    async def test_material_keeps_its_summary(self) -> None:
        plan = await _plan(_state(), ExploreTurnAnalysis(user_intent="material", question_summary="この図の意味"))

        assert plan.question_summary == "この図の意味"

    async def test_understood_after_a_question_proposes_moving_on_once(self) -> None:
        plan = await _plan(_state("わかった", explore_questions=_ASKED), ExploreTurnAnalysis(user_intent="understood"))

        assert plan.wrap_up is True
        assert plan.end_confirmation == "offered"

    async def test_understood_without_any_question_does_not_wrap_up(self) -> None:
        plan = await _plan(_state("わかった"), ExploreTurnAnalysis(user_intent="understood"))

        assert plan.wrap_up is False
        assert plan.end_confirmation is None

    async def test_does_not_wrap_up_twice(self) -> None:
        state = _state("わかった", explore_questions=_ASKED, wrap_up_offered=True)

        plan = await _plan(state, ExploreTurnAnalysis(user_intent="understood"))

        assert plan.wrap_up is False

    async def test_second_wish_to_end_confirms(self) -> None:
        plan = await _plan(
            _state("終わります", end_confirmation="offered"), ExploreTurnAnalysis(user_intent="end_session")
        )

        assert plan.end_confirmation == "confirmed"

    async def test_failed_analysis_answers_as_a_question_without_records(self) -> None:
        plan = await _plan(_state(), None)

        assert plan.user_intent == "question"
        assert plan.terms == []
        assert plan.question_summary == ""
        assert plan.topic == ""


def _llm(message_id: str | None = "ai-1") -> MagicMock:
    mock = MagicMock()
    mock.ainvoke = AsyncMock(return_value=AIMessage(content="答えです", id=message_id))
    return mock


async def _respond(state: LearningState, plan: Any, mock_llm: MagicMock) -> dict[str, Any]:
    with (
        patch("graph.nodes._explore_dialogue.llm", mock_llm),
        patch("graph.nodes._explore_dialogue.load_image_blocks", new=AsyncMock(return_value=[])),
    ):
        from graph.nodes._explore_dialogue import respond_explore

        return await respond_explore(state, plan)


class TestRespondExplore:
    async def test_answers_and_records_the_question_and_terms(self) -> None:
        state = _state()
        plan = await _plan(
            state,
            ExploreTurnAnalysis(
                user_intent="question",
                question_summary="二分探索とは",
                terms=[ExploreTermDraft(term="計算量", meaning="手間の目安")],
            ),
        )
        mock_llm = _llm(message_id=None)

        result = await _respond(state, plan, mock_llm)

        prompt = mock_llm.ainvoke.call_args.args[0][0].content
        assert "疑問に答える" in prompt
        answer = result["messages"][0]
        assert answer.id
        assert result["explore_questions"] == [{"question": "二分探索とは", "answer_message_id": answer.id}]
        assert result["explore_terms"] == [{"term": "計算量", "reading": "", "meaning": "手間の目安"}]
        assert result["explore_turn"] == {"user_intent": "question", "wrap_up": False}
        assert result["end_confirmation"] is None
        assert result["should_generate_note"] is False
        assert result["turn_count"] == 2
        assert mock_llm.ainvoke.call_args.kwargs["task"] == "explore-dialogue"

    async def test_wrap_up_turn_uses_the_proposal_section(self) -> None:
        state = _state("わかった", explore_questions=_ASKED)
        plan = await _plan(state, ExploreTurnAnalysis(user_intent="understood"))
        mock_llm = _llm()

        result = await _respond(state, plan, mock_llm)

        assert "自分の言葉で説明してみる" in mock_llm.ainvoke.call_args.args[0][0].content
        assert result["wrap_up_offered"] is True
        assert result["explore_questions"] == _ASKED

    async def test_confirmed_turn_calls_no_llm_and_adds_no_message(self) -> None:
        state = _state("終わります", end_confirmation="offered")
        plan = await _plan(state, ExploreTurnAnalysis(user_intent="end_session"))
        mock_llm = _llm()

        result = await _respond(state, plan, mock_llm)

        mock_llm.ainvoke.assert_not_called()
        assert "messages" not in result
        assert result["end_confirmation"] == "confirmed"


class TestExploreDialogueRouter:
    async def test_always_prepares_and_responds(self) -> None:
        prepare = AsyncMock(return_value="plan")
        respond = AsyncMock(return_value={"messages": []})
        with (
            patch("graph.nodes.explore_dialogue.prepare_explore_turn", new=prepare),
            patch("graph.nodes.explore_dialogue.respond_explore", new=respond),
        ):
            from graph.nodes.explore_dialogue import explore_dialogue

            await explore_dialogue(_state())

        respond.assert_awaited_once()
        assert respond.call_args.args[1] == "plan"
