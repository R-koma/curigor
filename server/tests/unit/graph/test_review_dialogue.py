from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from graph.output_schemas import ReviewTurnAnalysis
from graph.prompts.review import build_review_turn_section
from graph.review_progress import ReviewPointState, ReviewTurnPlan
from graph.state import LearningState

SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
NOTE_ID = UUID("00000000-0000-0000-0000-000000000001")


def _make_state(**overrides: object) -> LearningState:
    base: dict[str, object] = {
        "user_id": "user-abc",
        "dialogue_session_id": SESSION_ID,
        "note_id": NOTE_ID,
        "messages": [HumanMessage(content="二分探索は半分に絞る手法です")],
        "topic": "二分探索",
        "turn_count": 2,
        "should_generate_note": False,
        "session_type": "review",
        "note_content": "二分探索のノート本文",
        "note_summary": "二分探索の要約",
    }
    base.update(overrides)
    return cast(LearningState, base)


def _no_end() -> Any:
    return patch(
        "graph.nodes.review_dialogue.analyze_review_turn",
        AsyncMock(return_value=ReviewTurnAnalysis(wants_to_end_session=False)),
    )


def _patched(analysis: ReviewTurnAnalysis | None) -> tuple[MagicMock, tuple[Any, Any]]:
    mock_llm = MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう")))
    return mock_llm, (
        patch("graph.nodes.review_dialogue.llm", mock_llm),
        patch("graph.nodes.review_dialogue.analyze_review_turn", AsyncMock(return_value=analysis)),
    )


async def _run(state: LearningState, analysis: ReviewTurnAnalysis | None) -> tuple[MagicMock, dict[str, object]]:
    mock_llm, (p_llm, p_analysis) = _patched(analysis=analysis)
    with p_llm, p_analysis:
        from graph.nodes.review_dialogue import review_dialogue

        return mock_llm, await review_dialogue(state)


class TestReviewEndSession:
    async def test_review_answered_falls_back_to_earlier_replies_when_the_key_is_missing(self) -> None:
        state = _make_state(
            messages=[
                HumanMessage(content="二分探索"),
                AIMessage(content="覚えていることは？"),
                HumanMessage(content="半分に絞ります"),
                AIMessage(content="他には？"),
                HumanMessage(content="終わります"),
            ]
        )
        assert "review_answered" not in state
        _, result = await _run(state, ReviewTurnAnalysis(wants_to_end_session=True))
        assert result["review_answered"] is True

    async def test_never_sets_should_generate_note(self) -> None:
        _, result = await _run(_make_state(), ReviewTurnAnalysis(wants_to_end_session=True))
        assert result["should_generate_note"] is False

    async def test_first_wish_to_end_offers_and_points_to_the_button(self) -> None:
        mock_llm, result = await _run(_make_state(), ReviewTurnAnalysis(wants_to_end_session=True))
        assert result["end_confirmation"] == "offered"
        (messages,) = mock_llm.ainvoke.call_args.args
        assert "下のボタン" in messages[0].content

    async def test_wish_to_end_after_an_offer_confirms_without_the_llm(self) -> None:
        mock_llm, result = await _run(
            _make_state(end_confirmation="offered"), ReviewTurnAnalysis(wants_to_end_session=True)
        )
        mock_llm.ainvoke.assert_not_called()
        assert result["end_confirmation"] == "confirmed"
        assert "messages" not in result

    async def test_an_answer_marks_the_review_as_answered_and_clears_the_offer(self) -> None:
        _, result = await _run(_make_state(end_confirmation="offered"), ReviewTurnAnalysis(wants_to_end_session=False))
        assert result["end_confirmation"] is None
        assert result["review_answered"] is True

    async def test_a_wish_to_end_alone_does_not_count_as_an_answer(self) -> None:
        _, result = await _run(_make_state(), ReviewTurnAnalysis(wants_to_end_session=True))
        assert result["review_answered"] is False

    async def test_analysis_failure_is_treated_as_an_answer(self) -> None:
        _, result = await _run(_make_state(end_confirmation="offered"), None)
        assert result["end_confirmation"] is None
        assert result["review_answered"] is True

    async def test_prompt_no_longer_mentions_the_end_signal(self) -> None:
        from graph.prompts import REVIEW_SYSTEM_PROMPT

        assert "LEARNING_END" not in REVIEW_SYSTEM_PROMPT


class TestReviewDialogue:
    async def test_uses_review_system_prompt(self) -> None:
        mock_llm = MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう")))
        with patch("graph.nodes.review_dialogue.llm", mock_llm), _no_end():
            from graph.nodes.review_dialogue import review_dialogue

            await review_dialogue(_make_state())

        (messages,) = mock_llm.ainvoke.call_args.args
        assert isinstance(messages[0], SystemMessage)
        assert "復習パートナー" in messages[0].content

    async def test_increments_turn_count(self) -> None:
        with (
            patch(
                "graph.nodes.review_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう"))),
            ),
            _no_end(),
        ):
            from graph.nodes.review_dialogue import review_dialogue

            result = await review_dialogue(_make_state(turn_count=2))

        assert result["turn_count"] == 3

    async def test_prior_improvements_injected_into_prompt(self) -> None:
        mock_llm = MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう")))
        with patch("graph.nodes.review_dialogue.llm", mock_llm), _no_end():
            from graph.nodes.review_dialogue import review_dialogue

            await review_dialogue(_make_state(prior_improvements="計算量の見積もりが曖昧でした"))

        (messages,) = mock_llm.ainvoke.call_args.args
        assert "重点確認項目" in messages[0].content
        assert "計算量の見積もりが曖昧でした" in messages[0].content

    async def test_focus_aspects_injected_into_prompt(self) -> None:
        mock_llm = MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう")))
        with patch("graph.nodes.review_dialogue.llm", mock_llm), _no_end():
            from graph.nodes.review_dialogue import review_dialogue

            await review_dialogue(_make_state(review_focus_aspects=["計算量"]))

        (messages,) = mock_llm.ainvoke.call_args.args
        assert "計算量" in messages[0].content

    async def test_no_prior_improvements_omits_focus_section(self) -> None:
        mock_llm = MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="続けましょう")))
        with patch("graph.nodes.review_dialogue.llm", mock_llm), _no_end():
            from graph.nodes.review_dialogue import review_dialogue

            await review_dialogue(_make_state())

        (messages,) = mock_llm.ainvoke.call_args.args
        assert "重点確認項目" not in messages[0].content


def _plan_point(point_id: str, *, in_note: bool = True) -> ReviewPointState:
    return {
        "id": point_id,
        "point": f"要点{point_id}",
        "question": f"質問{point_id}は？",
        "expected": [f"期待{point_id}a", f"期待{point_id}b"],
        "source": "general",
        "aspect_id": None,
        "in_note": in_note,
        "status": "pending",
        "queued": False,
    }


def _queued(ids: list[str]) -> list[ReviewPointState]:
    return [{**_plan_point(i), "queued": True} for i in ids]


def _system_prompt(mock_llm: MagicMock) -> str:
    (messages,) = mock_llm.ainvoke.call_args.args
    return cast(str, messages[0].content)


def _status(updates: dict[str, object], point_id: str) -> str:
    points = cast(list[ReviewPointState], updates["review_points"])
    return next(p["status"] for p in points if p["id"] == point_id)


def _answer(*, explained: bool = False, ids: list[str] | None = None, end: bool = False) -> ReviewTurnAnalysis:
    return ReviewTurnAnalysis(
        wants_to_end_session=end, current_point_explained=explained, explained_point_ids=ids or []
    )


class TestReviewDialogueWithPlan:
    async def test_dialogue_without_review_points_keeps_the_old_prompt(self) -> None:
        llm, updates = await _run(_make_state(prior_improvements="改善点X"), _answer())
        assert "改善点X" in _system_prompt(llm)
        assert "review_points" not in updates
        assert "wrap_up_offered" not in updates

    async def test_wish_to_end_without_review_points_keeps_the_focus_section(self) -> None:
        from graph.prompts import REVIEW_END_SESSION_SECTION

        llm, _ = await _run(_make_state(prior_improvements="改善点X"), _answer(end=True))
        prompt = _system_prompt(llm)
        assert "改善点X" in prompt
        assert REVIEW_END_SESSION_SECTION in prompt

    async def test_plan_replaces_the_prior_improvements_section(self) -> None:
        state = _make_state(
            prior_improvements="改善点X", review_points=_queued(["p1", "p2"]), review_current_point_id="p1"
        )
        llm, _ = await _run(state, _answer(explained=True))
        prompt = _system_prompt(llm)
        assert "改善点X" not in prompt
        assert "質問p2は？" in prompt

    async def test_opener_answer_skips_recalled_points_and_asks_the_next(self) -> None:
        points = [_plan_point(f"p{i}") for i in range(1, 7)]
        llm, updates = await _run(_make_state(review_points=points), _answer(ids=["p1"]))
        assert _status(updates, "p1") == "explained"
        assert updates["review_current_point_id"] == "p2"
        assert "質問p2は？" in _system_prompt(llm)

    async def test_dialogue_hints_once_then_explains(self) -> None:
        state = _make_state(review_points=_queued(["p1", "p2"]), review_current_point_id="p1")
        llm, first = await _run(state, _answer())
        assert first["review_current_point_id"] == "p1"
        assert _status(first, "p1") == "hinted"
        assert "ヒント" in _system_prompt(llm)

        state = _make_state(review_points=first["review_points"], review_current_point_id="p1")
        llm, second = await _run(state, _answer())
        assert _status(second, "p1") == "not_explained"
        assert second["review_current_point_id"] == "p2"
        prompt = _system_prompt(llm)
        assert "正しい説明" in prompt
        assert "期待p1a" in prompt
        assert "質問p2は？" in prompt

    async def test_dialogue_offers_wrap_up_after_last_point(self) -> None:
        state = _make_state(review_points=_queued(["p1"]), review_current_point_id="p1")
        llm, updates = await _run(state, _answer(explained=True))
        assert updates["end_confirmation"] == "offered"
        assert updates["wrap_up_offered"] is True
        assert updates["review_current_point_id"] is None
        assert "下のボタン" in _system_prompt(llm)

    async def test_declined_wrap_up_continues_with_an_unasked_candidate(self) -> None:
        points = [*_queued(["p1"]), _plan_point("p2")]
        points[0]["status"] = "explained"
        state = _make_state(review_points=points, review_current_point_id=None, wrap_up_offered=True)
        llm, updates = await _run(state, _answer())
        assert updates["review_current_point_id"] == "p2"
        assert updates["wrap_up_offered"] is True
        assert updates["end_confirmation"] is None
        assert "質問p2は？" in _system_prompt(llm)

    async def test_review_turn_updates_write_only_progress_keys(self) -> None:
        state = _make_state(review_points=_queued(["p1", "p2"]), review_current_point_id="p1")
        _, updates = await _run(state, _answer(explained=True))
        assert set(updates) == {
            "turn_count",
            "should_generate_note",
            "end_confirmation",
            "review_answered",
            "review_points",
            "review_current_point_id",
            "wrap_up_offered",
            "messages",
        }

    async def test_wish_to_end_uses_the_end_section_and_keeps_the_hint_unused(self) -> None:
        state = _make_state(review_points=_queued(["p1", "p2"]), review_current_point_id="p1")
        llm, updates = await _run(state, _answer(end=True, ids=["p2"]))
        prompt = _system_prompt(llm)
        assert "セッションを終えたい" in prompt
        assert "質問p1は？" not in prompt
        assert _status(updates, "p1") == "pending"
        assert _status(updates, "p2") == "explained"
        assert updates["review_current_point_id"] == "p1"
        assert updates["wrap_up_offered"] is False

    async def test_confirmed_turn_still_records_the_answer(self) -> None:
        state = _make_state(
            review_points=_queued(["p1", "p2"]), review_current_point_id="p1", end_confirmation="offered"
        )
        llm, updates = await _run(state, _answer(end=True, explained=True))
        llm.ainvoke.assert_not_called()
        assert updates["end_confirmation"] == "confirmed"
        assert _status(updates, "p1") == "explained"

    async def test_declined_end_offer_asks_the_current_point_again_without_using_the_hint(self) -> None:
        state = _make_state(
            review_points=_queued(["p1", "p2"]), review_current_point_id="p1", end_confirmation="offered"
        )
        llm, updates = await _run(state, _answer(ids=["p2"]))
        assert _status(updates, "p1") == "pending"
        assert _status(updates, "p2") == "pending"
        assert updates["review_current_point_id"] == "p1"
        assert updates["end_confirmation"] is None
        prompt = _system_prompt(llm)
        assert "質問p1は？" in prompt
        assert "このターン: ヒントを出す" not in prompt

    async def test_declined_wrap_up_offer_still_records_the_answer(self) -> None:
        points = [*_queued(["p1"]), _plan_point("p2")]
        points[0]["status"] = "explained"
        state = _make_state(
            review_points=points, review_current_point_id=None, wrap_up_offered=True, end_confirmation="offered"
        )
        _, updates = await _run(state, _answer(ids=["p2"]))
        assert _status(updates, "p2") == "explained"

    async def test_analysis_failure_asks_the_current_point_again(self) -> None:
        state = _make_state(review_points=_queued(["p1", "p2"]), review_current_point_id="p1")
        llm, updates = await _run(state, None)
        assert _status(updates, "p1") == "pending"
        assert updates["review_current_point_id"] == "p1"
        assert "質問p1は？" in _system_prompt(llm)


def _plan(**overrides: object) -> ReviewTurnPlan:
    base: dict[str, object] = {
        "points": [],
        "current_point_id": None,
        "hint_point": None,
        "explain_point": None,
        "ask_point": None,
        "wrap_up": False,
    }
    base.update(overrides)
    return ReviewTurnPlan(**base)  # type: ignore[arg-type]


class TestBuildReviewTurnSection:
    def test_no_plan_point_gives_the_free_review(self) -> None:
        assert build_review_turn_section(_plan()) == ""

    def test_hint_keeps_the_answer_hidden(self) -> None:
        section = build_review_turn_section(_plan(hint_point=_plan_point("p1")))
        assert "ヒント" in section
        assert "この指示は対話のルールより優先する" in section
        assert "ユーザーに見せない" in section
        assert "期待p1a" in section

    def test_ask_uses_the_plan_question_without_the_expected_answer_in_it(self) -> None:
        section = build_review_turn_section(_plan(ask_point=_plan_point("p2")))
        assert "質問p2は？" in section
        assert "判定に使う。ユーザーに見せない" in section
        assert "この指示は対話のルールより優先する" in section

    def test_explanation_of_a_point_outside_the_note_teaches_from_scratch(self) -> None:
        section = build_review_turn_section(
            _plan(explain_point=_plan_point("p1", in_note=False), ask_point=_plan_point("p2"))
        )
        assert "初めて知る前提" in section
        assert "2〜3 文" in section
        assert "質問p2は？" in section

    def test_wrap_up_asks_no_new_question(self) -> None:
        section = build_review_turn_section(_plan(explain_point=_plan_point("p1"), wrap_up=True))
        assert "新しい質問をしない" in section
        assert "下のボタン" in section
        assert "初めて知る前提" not in section
