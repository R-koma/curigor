from typing import Any

from graph.output_schemas import ReviewPlanPointDraft, ReviewPointSource
from graph.review_plan import (
    CarryoverPoint,
    ReviewPlanPoint,
    ReviewResult,
    ReviewResultStatus,
    carryover_points,
    order_review_points,
    sanitize_plan_points,
)


def _point(
    point_id: str, point: str = "要点", source: ReviewPointSource = "general", aspect_id: str | None = None
) -> ReviewPlanPoint:
    return {
        "id": point_id,
        "point": point,
        "question": f"{point}の問い",
        "expected": ["x"],
        "source": source,
        "aspect_id": aspect_id,
        "in_note": True,
    }


def _result(point_id: str, point: str, status: ReviewResultStatus) -> ReviewResult:
    return {"point_id": point_id, "point": point, "question": f"{point}の問い", "status": status, "aspect_id": None}


def _draft(**overrides: Any) -> ReviewPlanPointDraft:
    fields: dict[str, Any] = {
        "point": "要点",
        "question": "問い",
        "expected": ["x"],
        "source": "general",
        "in_note": True,
    }
    return ReviewPlanPointDraft(**{**fields, **overrides})


def test_carryover_keeps_unexplained_and_unasked_results() -> None:
    results = [_result("p1", "A", "not_explained"), _result("p2", "B", "explained"), _result("p3", "C", "not_asked")]
    assert [c["point"] for c in carryover_points(None, results)] == ["A", "C"]


def test_carryover_keeps_previous_carryover_that_was_not_in_this_session() -> None:
    plan = [_point("p1", "X", source="carryover"), _point("p2", "Y", source="covered")]
    assert [c["point"] for c in carryover_points(plan, [_result("p9", "Z", "explained")])] == ["X"]


def test_carryover_dedupes_by_point_text() -> None:
    plan = [_point("p1", "A", source="carryover")]
    assert len(carryover_points(plan, [_result("q1", "A", "not_explained")])) == 1


def test_carryover_keeps_previous_carryover_whose_id_collides_with_a_result() -> None:
    plan = [_point("p1", "Old", source="carryover")]
    results = [_result("p1", "X", "explained"), _result("p2", "B", "not_explained")]
    assert [c["point"] for c in carryover_points(plan, results)] == ["B", "Old"]


def test_carryover_drops_previous_carryover_explained_in_the_results() -> None:
    plan = [_point("p7", "A", source="carryover")]
    assert carryover_points(plan, [_result("p1", "A", "explained")]) == []


def test_carryover_assigns_sequential_keys() -> None:
    results = [_result("p1", "A", "not_explained"), _result("p2", "B", "not_asked")]
    assert [c["key"] for c in carryover_points(None, results)] == ["c1", "c2"]


def test_sanitize_drops_unknown_aspect_ids() -> None:
    [p] = sanitize_plan_points([_draft(aspect_id="a9")], {"aspects": [{"name": "x"}]}, [])
    assert p["aspect_id"] is None and p["id"] == "p1"


def test_sanitize_keeps_known_aspect_ids() -> None:
    [p] = sanitize_plan_points([_draft(aspect_id="a1")], {"aspects": [{"name": "x"}]}, [])
    assert p["aspect_id"] == "a1"


def test_sanitize_drops_points_without_expected() -> None:
    assert sanitize_plan_points([_draft(expected=[])], None, []) == []


def test_sanitize_appends_missing_carryover() -> None:
    carry: list[CarryoverPoint] = [
        {"key": "c1", "point": "A", "question": "前の問い", "aspect_id": None, "expected": []}
    ]
    points = sanitize_plan_points([_draft(source="covered")], None, carry)
    [added] = [p for p in points if p["source"] == "carryover"]
    assert (added["point"], added["question"], added["expected"]) == ("A", "前の問い", [])


def test_sanitize_keeps_carryover_point_text_and_new_question() -> None:
    carry: list[CarryoverPoint] = [
        {"key": "c1", "point": "A", "question": "前の問い", "aspect_id": None, "expected": []}
    ]
    [p] = sanitize_plan_points([_draft(carryover_key="c1", point="A'", question="新しい問い")], None, carry)
    assert (p["point"], p["question"], p["source"]) == ("A", "新しい問い", "carryover")


def test_sanitize_caps_points_but_not_carryover() -> None:
    carry: list[CarryoverPoint] = [{"key": "c1", "point": "A", "question": "q", "aspect_id": None, "expected": []}]
    points = sanitize_plan_points([_draft(point=f"n{i}") for i in range(15)], None, carry)
    assert len(points) == 10
    assert sum(p["source"] == "carryover" for p in points) == 1
    assert [p["id"] for p in points] == [f"p{i}" for i in range(1, 11)]


def test_order_puts_memo_aspects_after_focused_aspects_and_before_carryover() -> None:
    pts = [
        _point("p1", source="carryover"),
        _point("p2", source="covered", aspect_id="a3-2"),
        _point("p3", source="covered", aspect_id="a1"),
    ]
    assert [p["id"] for p in order_review_points(pts, ["a1"], ["a3"])] == ["p3", "p2", "p1"]
    assert [p["id"] for p in order_review_points(pts, None, ["a3-2"])] == ["p2", "p1", "p3"]


def test_order_puts_focused_aspects_first_then_source_priority() -> None:
    pts = [
        _point("p1", source="covered", aspect_id="a2-1"),
        _point("p2", source="carryover"),
        _point("p3", source="improvement"),
    ]
    assert [p["id"] for p in order_review_points(pts, ["a2"])] == ["p1", "p2", "p3"]
    assert [p["id"] for p in order_review_points(pts, None)] == ["p2", "p3", "p1"]
    assert [p["id"] for p in order_review_points(pts, [])] == ["p2", "p3", "p1"]


def test_sanitize_does_not_keep_unmatched_carryover_source() -> None:
    [p] = sanitize_plan_points([_draft(source="carryover", carryover_key="c9")], None, [])
    assert p["source"] == "general"


def test_carryover_takes_expected_from_the_previous_plan_point() -> None:
    first = _point("p1", "A")
    first["expected"] = ["e1", "e2"]
    plan = [first, _point("p2", "B", source="carryover")]
    results = [_result("p1", "A", "not_explained")]
    carried = carryover_points(plan, results)
    assert [(c["point"], c["expected"]) for c in carried] == [("A", ["e1", "e2"]), ("B", ["x"])]


def test_carryover_without_a_previous_plan_point_has_no_expected() -> None:
    assert carryover_points(None, [_result("p1", "A", "not_asked")])[0]["expected"] == []


def test_sanitize_fills_empty_carryover_expected_from_the_previous_plan() -> None:
    carry: list[CarryoverPoint] = [{"key": "c1", "point": "A", "question": "q", "aspect_id": None, "expected": ["e"]}]
    [p] = sanitize_plan_points([_draft(carryover_key="c1", expected=[])], None, carry)
    assert p["expected"] == ["e"]


def test_sanitize_prefers_the_new_expected_for_carryover() -> None:
    carry: list[CarryoverPoint] = [{"key": "c1", "point": "A", "question": "q", "aspect_id": None, "expected": ["e"]}]
    [p] = sanitize_plan_points([_draft(carryover_key="c1", expected=["new"])], None, carry)
    assert p["expected"] == ["new"]


def test_sanitize_appended_carryover_keeps_the_previous_expected() -> None:
    carry: list[CarryoverPoint] = [{"key": "c1", "point": "A", "question": "q", "aspect_id": None, "expected": ["e"]}]
    points = sanitize_plan_points([_draft(source="covered")], None, carry)
    [added] = [p for p in points if p["source"] == "carryover"]
    assert added["expected"] == ["e"]
