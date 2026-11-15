from __future__ import annotations

import copy
from collections import Counter
from typing import Any

from evals import map_turn_analysis_dataset as dataset
from evals.dataset import SourceTrace, get_source_trace, load_source_records

_LAST = "ええと、スタックは後入れ先出しです。"


def _source(
    record_id: str = "s1__t2", *, route: str | None = "map", captured_by: str | None = "capture", **graph: Any
) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if route:
        meta["route"] = route
    if captured_by:
        meta["captured_by"] = captured_by
    return {
        "id": record_id,
        "turn": 2,
        "meta": meta,
        "input": {
            "conversation_history": [
                {"role": "assistant", "content": "説明してみてください。"},
                {"role": "user", "content": _LAST},
            ],
            "graph_state": {"topic": "スタック", "depth_map": {"aspects": []}, **graph},
        },
        "output": "応答",
    }


def _row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": "s1__t2",
        "source": "real",
        "base": "s1__t2",
        "expected": None,
        "unclear": [],
        "note": "",
        "annotated_at": None,
    }
    return row | overrides


def _handwritten(**overrides: Any) -> dict[str, Any]:
    row = _row(id="hw-1", source="handwritten", last_user_message="キューも同じです。", category="misconception")
    return row | overrides


def _trace(source: dict[str, Any]) -> SourceTrace:
    return get_source_trace(source["id"], {source["id"]: source})


def test_resolve_trace_keeps_a_real_row_as_is() -> None:
    source = _source()

    trace = dataset.resolve_trace(_row(), {"s1__t2": source})

    assert trace.input == source["input"]


def test_resolve_trace_replaces_only_the_last_message_of_a_handwritten_row() -> None:
    source = _source()
    before = copy.deepcopy(source)

    trace = dataset.resolve_trace(_handwritten(), {"s1__t2": source})

    history = trace.input["conversation_history"]
    assert history[-1] == {"role": "user", "content": "キューも同じです。"}
    assert history[0] == before["input"]["conversation_history"][0]
    assert trace.input["graph_state"] == before["input"]["graph_state"]
    assert source == before


def test_resolve_trace_rejects_an_unknown_base() -> None:
    try:
        dataset.resolve_trace(_row(base="missing"), {})
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("ValueError が出なかった")


def test_blocker_accepts_a_captured_map_turn() -> None:
    assert dataset.blocker(_trace(_source())) is None


def test_blocker_stops_the_legacy_route() -> None:
    assert dataset.blocker(_trace(_source(route=None))) is not None


def test_blocker_stops_a_record_not_captured_by_capture() -> None:
    assert dataset.blocker(_trace(_source(captured_by=None))) is not None


def test_blocker_stops_the_start_of_the_question_phase() -> None:
    assert dataset.blocker(_trace(_source(start_requested=True))) is not None


def test_seed_real_rows_adds_unlabeled_rows_for_usable_records_only() -> None:
    sources = {
        "a": _source("a"),
        "b": _source("b", route=None),
        "c": _source("c", start_requested=True),
    }

    rows = dataset.seed_real_rows(sources, [])

    assert [r["id"] for r in rows] == ["a"]
    assert rows[0] == _row(id="a", base="a")
    assert dataset.validate_row(rows[0]) == []


def test_seed_real_rows_skips_a_base_that_already_has_a_real_row() -> None:
    sources = {"a": _source("a"), "b": _source("b")}
    existing = [_row(id="a", base="a"), _handwritten(base="b")]

    rows = dataset.seed_real_rows(sources, existing)

    assert [r["base"] for r in rows] == ["b"]


def test_validate_row_accepts_labeled_rows_and_unclear_fields() -> None:
    labeled = _row(expected={"has_misconception": True, "user_intent": "explanation"})
    half = _row(expected={"has_misconception": None, "user_intent": "question"}, unclear=["has_misconception"])

    assert dataset.validate_row(labeled) == []
    assert dataset.validate_row(half) == []
    assert dataset.validate_row(_handwritten()) == []


def test_validate_row_reports_problems() -> None:
    bad_intent = _row(expected={"has_misconception": False, "user_intent": "chat"})
    empty_message = _handwritten(last_user_message=" ")
    unknown_field = _row(expected={"has_misconception": None, "user_intent": "question"}, unclear=["tone"])
    unclear_with_value = _row(
        expected={"has_misconception": True, "user_intent": "question"}, unclear=["has_misconception"]
    )
    bad_source = _row(source="synthetic")

    assert any("user_intent" in p for p in dataset.validate_row(bad_intent))
    assert any("last_user_message" in p for p in dataset.validate_row(empty_message))
    assert any("tone" in p for p in dataset.validate_row(unknown_field))
    assert any("has_misconception" in p for p in dataset.validate_row(unclear_with_value))
    assert any("source" in p for p in dataset.validate_row(bad_source))


def test_repository_dataset_is_consistent() -> None:
    rows = dataset.load_rows()
    sources = load_source_records()

    assert rows
    assert [p for row in rows for p in dataset.validate_row(row)] == []
    assert [i for i, n in Counter(r["id"] for r in rows).items() if n > 1] == []
    assert [r["id"] for r in rows if r["base"] not in sources] == []
    assert dataset.USER_INTENTS == (
        "explanation",
        "dont_know",
        "partial_dont_know",
        "question",
        "exhausted",
        "end_session",
    )
    assert dataset.FIELDS == ("has_misconception", "user_intent")


def test_repository_rows_can_all_be_replayed() -> None:
    sources = load_source_records()

    blocked = {
        r["id"]: reason
        for r in dataset.load_rows()
        if (reason := dataset.blocker(get_source_trace(r["base"], sources)))
    }

    assert blocked == {}


def test_handwritten_rows_name_their_aim_and_do_not_lean_on_one_base() -> None:
    handwritten = [r for r in dataset.load_rows() if r["source"] == "handwritten"]

    assert {r["category"] for r in handwritten} <= {"misconception", *dataset.USER_INTENTS}
    assert max(Counter(r["base"] for r in handwritten).values()) <= 3


def _handwritten_messages(category: str) -> dict[str, str]:
    return {
        r["id"]: r["last_user_message"]
        for r in dataset.load_rows()
        if r["source"] == "handwritten" and r["category"] == category
    }


def test_handwritten_rows_keep_the_planned_count_per_category() -> None:
    counts = Counter(r["category"] for r in dataset.load_rows() if r["source"] == "handwritten")

    assert counts == {
        "misconception": 30,
        "exhausted": 15,
        "end_session": 15,
        "dont_know": 9,
        "partial_dont_know": 6,
        "question": 6,
    }
    assert all(r["expected"] is None for r in dataset.load_rows())


def test_exhausted_rows_do_not_share_one_template() -> None:
    messages = list(_handwritten_messages("exhausted").values())

    assert sum("これ以上" in m for m in messages) <= 3
    assert sum("というところまで" in m for m in messages) <= 2
    assert sum(not any(w in m for w in ("思いつ", "出てこ", "出てきません", "できません")) for m in messages) >= 8
    assert sum(len(m) <= 20 for m in messages) >= 2
    assert sum(len(m) >= 60 for m in messages) >= 1


def test_exhausted_rows_do_not_read_as_partly_not_knowing() -> None:
    messages = _handwritten_messages("exhausted")

    assert [i for i, m in messages.items() if "までしか分かりません" in m or "しか分かりません" in m] == []


def test_question_rows_do_not_all_ask_for_a_difference() -> None:
    messages = list(_handwritten_messages("question").values())

    assert sum("違いを教えて" in m for m in messages) == 0
    assert len({m[-12:] for m in messages}) == len(messages)


def test_the_arguable_perspective_row_is_replaced() -> None:
    assert "遠近法の一種" not in _handwritten_messages("misconception")["hw-038"]
