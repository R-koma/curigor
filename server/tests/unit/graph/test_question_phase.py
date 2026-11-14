from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from graph.output_schemas import MapDialogueTurnAnalysis, MapUserIntent
from graph.question_phase import (
    START_QUESTIONS_KEY,
    pending_question_count,
    pending_question_ids,
    plan_phase_step,
    start_requested,
)
from graph.state import DepthMapState, MapAspectProgress, MapStage, PhaseStepRecord


def _map(core: tuple[str, ...] = ("a", "b", "c", "d"), other: tuple[str, ...] = ("e",)) -> DepthMapState:
    return {
        "topic": "T",
        "aspects": [
            {
                "id": aspect_id,
                "name": aspect_id.upper(),
                "is_core": aspect_id in core,
                "defined_question": "D",
                "reasoned_question": "R",
                "applied_question": "P",
            }
            for aspect_id in (*core, *other)
        ],
    }


def _covered(**stages: MapStage) -> list[MapAspectProgress]:
    return [{"aspect_id": aspect_id, "reached_stage": stage} for aspect_id, stage in stages.items()]


def _analysis(intent: MapUserIntent = "explanation", *, misconception: bool = False) -> MapDialogueTurnAnalysis:
    return MapDialogueTurnAnalysis(
        user_intent=intent,
        observations=[],
        has_misconception=misconception,
        error_summary="E" if misconception else "",
        response_mode="reinforce" if misconception else "deepen",
        selected_aspect_id="a",
    )


def _free(**extra: Any) -> dict[str, Any]:
    return {
        "dialogue_phase": "free",
        "depth_map": _map(),
        "messages": [AIMessage(content="声かけ"), HumanMessage(content="説明")],
        **extra,
    }


def _questions(
    queue: list[str],
    index: int,
    *,
    previous: PhaseStepRecord | None = None,
    asked: list[str] | None = None,
    hinted: bool = False,
) -> dict[str, Any]:
    step = previous or _step(None, queue=queue, index=index, total=len(queue))
    return {
        "question_hinted": hinted,
        "dialogue_phase": "questions",
        "depth_map": _map(),
        "question_queue": queue,
        "question_index": index,
        "asked_aspect_ids": asked if asked is not None else queue[: index + 1],
        "turn_analysis": {
            "response_mode": "expand",
            "selected_aspect": "",
            "has_misconception": False,
            "error_summary": "",
            "phase_step": step,
        },
    }


def _step(kind: Any, *, queue: list[str], index: int | None, total: int, **extra: Any) -> PhaseStepRecord:
    record = PhaseStepRecord(
        kind=kind,
        phase="questions",
        queue=queue,
        index=index,
        asked=queue[: (index or 0) + 1],
        total=total,
        shortened=False,
        offer_end=False,
        unknown_streak=0,
        start_requested=False,
    )
    record.update(extra)  # type: ignore[typeddict-item]
    return record


def _plan(
    values: dict[str, Any],
    analysis: MapDialogueTurnAnalysis | None,
    covered: Any = (),
    start: bool = False,
    fallback_intent: MapUserIntent = "explanation",
) -> PhaseStepRecord:
    step = plan_phase_step(values, analysis, _map(), list(covered), start=start, fallback_intent=fallback_intent)
    assert step is not None
    return step


def test_pending_ids_take_core_below_reasoned_in_map_order_capped_at_three() -> None:
    depth_map = _map()
    assert pending_question_ids(depth_map, [], []) == ["a", "b", "c"]
    assert pending_question_ids(depth_map, _covered(a="reasoned"), []) == ["b", "c", "d"]
    assert pending_question_ids(depth_map, _covered(a="applied", b="defined"), []) == ["b", "c", "d"]
    assert pending_question_ids(depth_map, _covered(b="defined"), ["b"]) == ["a", "c", "d"]
    assert pending_question_ids(depth_map, _covered(e="mentioned"), ["a", "b", "c", "d"]) == []


def test_pending_count_is_none_without_phase_key() -> None:
    values = _free()
    del values["dialogue_phase"]
    assert pending_question_count(values) is None


def test_pending_count_is_none_before_first_explanation() -> None:
    values = _free(
        messages=[HumanMessage(content="聞き取り"), AIMessage(content="声かけ")],
        intake_message_count=1,
    )
    assert pending_question_count(values) is None


def test_pending_count_is_none_until_the_current_map_has_coverage() -> None:
    after_topic_change = _free(
        messages=[
            AIMessage(content="声かけ"),
            HumanMessage(content="前のトピックの説明"),
            AIMessage(content="切り替えた"),
        ],
        map_covered=[],
        asked_aspect_ids=[],
    )
    assert pending_question_count(after_topic_change) is None
    only_dont_know = _free(messages=[AIMessage(content="声かけ"), HumanMessage(content="わからない")])
    assert pending_question_count(only_dont_know) is None


def test_pending_count_is_none_in_questions_phase() -> None:
    values = {**_questions(["a", "b"], 0), "messages": [HumanMessage(content="説明")]}
    assert pending_question_count(values) is None


def test_pending_count_counts_after_first_explanation() -> None:
    assert pending_question_count(_free(map_covered=_covered(a="mentioned"))) == 3
    assert pending_question_count(_free(map_covered=_covered(a="reasoned", b="reasoned", c="applied"))) == 1
    assert (
        pending_question_count(_free(map_covered=_covered(e="mentioned"), asked_aspect_ids=["a", "b", "c", "d"])) == 0
    )


def test_start_requested_only_in_free_phase() -> None:
    marked = [HumanMessage(content="質問をどうぞ", additional_kwargs={START_QUESTIONS_KEY: True})]
    assert start_requested({"dialogue_phase": "free", "messages": marked})
    assert not start_requested({"messages": marked})
    assert not start_requested({"dialogue_phase": "questions", "messages": marked})
    assert not start_requested({"dialogue_phase": "free", "messages": [HumanMessage(content="説明")]})


def test_step_is_none_without_phase_key() -> None:
    assert plan_phase_step({"depth_map": _map()}, _analysis(), _map(), [], start=False) is None


def test_free_explanation_listens() -> None:
    step = _plan(_free(), _analysis())
    assert (step["kind"], step["phase"], step["queue"], step["index"]) == ("listen", "free", [], None)
    assert not step["offer_end"]


def test_free_misconception_corrects() -> None:
    assert _plan(_free(), _analysis(misconception=True))["kind"] == "correct"


def test_free_question_answers() -> None:
    assert _plan(_free(), _analysis("question"))["kind"] == "answer"


def test_free_dont_know_keeps_existing_section() -> None:
    for intent in ("dont_know", "partial_dont_know", "end_session"):
        step = _plan(_free(), _analysis(intent))
        assert step["kind"] is None
        assert step["phase"] == "free"


def test_free_analysis_failure_listens() -> None:
    assert _plan(_free(), None)["kind"] == "listen"


def test_start_builds_queue_and_asks_first() -> None:
    step = _plan(_free(), None, start=True)
    assert step["kind"] == "ask"
    assert step["phase"] == "questions"
    assert step["queue"] == ["a", "b", "c"]
    assert step["index"] == 0
    assert step["asked"] == ["a"]
    assert step["total"] == 3
    assert step["start_requested"]


def test_exhausted_starts_questions_like_button() -> None:
    step = _plan(_free(), _analysis("exhausted"), _covered(a="reasoned"))
    assert (step["kind"], step["queue"], step["asked"], step["total"]) == ("ask", ["b", "c", "d"], ["b"], 3)
    assert not step["start_requested"]


def test_start_without_candidates_offers_end() -> None:
    covered = _covered(a="reasoned", b="reasoned", c="reasoned", d="applied")
    step = _plan(_free(), None, covered, start=True)
    assert (step["kind"], step["phase"], step["offer_end"], step["total"]) == ("finish", "free", True, 0)
    assert step["queue"] == []


def test_single_core_asks_one() -> None:
    depth_map = _map(core=("a",), other=("b", "c"))
    step = plan_phase_step(_free(depth_map=depth_map), None, depth_map, [], start=True)
    assert step is not None
    assert (step["kind"], step["queue"], step["total"]) == ("ask", ["a"], 1)


def test_answer_advances_even_with_misconception() -> None:
    step = _plan(_questions(["a", "b", "c"], 0), _analysis(misconception=True))
    assert (step["kind"], step["index"], step["asked"], step["total"]) == ("ask", 1, ["a", "b"], 3)
    assert step["unknown_streak"] == 0


def test_analysis_failure_advances() -> None:
    step = _plan(_questions(["a", "b", "c"], 1), None)
    assert (step["kind"], step["index"], step["asked"]) == ("ask", 2, ["a", "b", "c"])


def test_exhausted_skips_the_item() -> None:
    assert _plan(_questions(["a", "b"], 0), _analysis("exhausted"))["index"] == 1


def test_first_dont_know_hints_and_second_advances() -> None:
    queue = ["a", "b", "c"]
    first = _plan(_questions(queue, 0), _analysis("dont_know"))
    assert (first["kind"], first["index"], first["unknown_streak"], first["asked"]) == ("hint", 0, 1, ["a"])
    assert first.get("hinted") is True

    second = _plan(_questions(queue, 0, previous=first, hinted=True), _analysis("partial_dont_know"))
    assert (second["kind"], second["index"], second["unknown_streak"]) == ("ask", 1, 2)
    assert second.get("hinted") is False


def test_second_dont_know_advances_after_an_intervening_turn() -> None:
    queue = ["a", "b", "c"]
    reask = _plan(_questions(queue, 0, hinted=True), _analysis("question"))
    assert (reask["kind"], reask.get("hinted")) == ("reask", True)
    ending = _plan(_questions(queue, 0, hinted=True), _analysis("end_session"))
    assert (ending["kind"], ending.get("hinted")) == (None, True)

    after_reask = _plan(_questions(queue, 0, previous=reask, hinted=True), _analysis("dont_know"))
    assert (after_reask["kind"], after_reask["index"], after_reask["unknown_streak"]) == ("ask", 1, 2)


def test_analysis_failure_uses_the_keyword_intent() -> None:
    queue = ["a", "b", "c"]
    hint = _plan(_questions(queue, 0), None, fallback_intent="dont_know")
    assert (hint["kind"], hint["index"], hint["asked"]) == ("hint", 0, ["a"])

    free = _plan(_free(), None, fallback_intent="dont_know")
    assert (free["kind"], free["phase"]) == (None, "free")

    exhausted = _plan(_free(), None, fallback_intent="exhausted")
    assert (exhausted["kind"], exhausted["phase"]) == ("ask", "questions")


def test_dont_know_count_resets_on_next_item() -> None:
    queue = ["a", "b", "c"]
    advanced = _step("ask", queue=queue, index=1, total=3, unknown_streak=2)
    step = _plan(_questions(queue, 1, previous=advanced), _analysis("dont_know"))
    assert (step["kind"], step["index"], step["unknown_streak"]) == ("hint", 1, 1)


def test_question_stays_on_item() -> None:
    step = _plan(_questions(["a", "b"], 0), _analysis("question"))
    assert (step["kind"], step["index"], step["queue"], step["asked"]) == ("reask", 0, ["a", "b"], ["a"])


def test_end_session_keeps_position() -> None:
    step = _plan(_questions(["a", "b"], 1), _analysis("end_session"))
    assert (step["kind"], step["phase"], step["index"], step["total"]) == (None, "questions", 1, 2)


def test_later_item_reached_is_skipped_and_marked_shortened() -> None:
    step = _plan(_questions(["a", "b", "c"], 0), _analysis(), _covered(b="reasoned"))
    assert (step["kind"], step["queue"], step["index"], step["asked"]) == ("ask", ["a", "c"], 1, ["a", "c"])
    assert step["shortened"]
    assert step["total"] == 3


def test_all_later_items_reached_finishes_shortened() -> None:
    step = _plan(_questions(["a", "b", "c"], 0), _analysis(), _covered(b="reasoned", c="applied"))
    assert (step["kind"], step["shortened"], step["offer_end"]) == ("finish", True, True)


def test_last_item_finishes_and_returns_to_free() -> None:
    step = _plan(_questions(["a", "b", "c"], 2), _analysis())
    assert step["kind"] == "finish"
    assert step["offer_end"]
    assert step["phase"] == "free"
    assert step["queue"] == []
    assert step["index"] is None
    assert step["total"] == 3
    assert not step["shortened"]


def test_asked_items_do_not_return_after_finish() -> None:
    step = _plan(_questions(["a", "b", "c"], 2), _analysis())
    assert pending_question_ids(_map(), _covered(a="defined"), step["asked"]) == ["d"]
