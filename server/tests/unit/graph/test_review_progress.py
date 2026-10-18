from graph.review_plan import ReviewPlanPoint
from graph.review_progress import (
    ReviewPointState,
    ReviewTurnInput,
    ReviewTurnPlan,
    initial_review_points,
    plan_review_turn,
    review_results,
)


def _point(point_id: str) -> ReviewPlanPoint:
    return {
        "id": point_id,
        "point": f"要点 {point_id}",
        "question": f"質問 {point_id}",
        "expected": ["期待"],
        "source": "general",
        "aspect_id": None,
        "in_note": True,
    }


def _queued(ids: list[str]) -> list[ReviewPointState]:
    points = initial_review_points([_point(i) for i in ids])
    return [{**p, "queued": True} for p in points]


def _status(plan: ReviewTurnPlan, point_id: str) -> str:
    return next(p["status"] for p in plan.points if p["id"] == point_id)


def _set(points: list[ReviewPointState], point_id: str, status: str) -> list[ReviewPointState]:
    return [{**p, "status": status} if p["id"] == point_id else p for p in points]  # type: ignore[typeddict-item]


def test_first_answer_marks_recalled_points_and_queues_the_rest() -> None:
    pts = initial_review_points([_point(f"p{i}") for i in range(1, 7)])
    plan = plan_review_turn(pts, None, ReviewTurnInput(False, ["p1"]), wrap_up_offered=False)
    assert _status(plan, "p1") == "explained"
    assert [p["id"] for p in plan.points if p["queued"]] == ["p2", "p3", "p4", "p5"]
    assert plan.ask_point is not None
    assert plan.ask_point["id"] == "p2" and plan.current_point_id == "p2"


def test_does_not_mutate_input_points() -> None:
    pts = initial_review_points([_point("p1"), _point("p2")])
    plan_review_turn(pts, None, ReviewTurnInput(False, ["p1"]), wrap_up_offered=False)
    assert all(p["status"] == "pending" and not p["queued"] for p in pts)


def test_insufficient_answer_gives_one_hint_then_explains() -> None:
    pts = _queued(["p1", "p2"])
    first = plan_review_turn(pts, "p1", ReviewTurnInput(False, []), wrap_up_offered=False)
    assert first.hint_point is not None
    assert first.hint_point["id"] == "p1" and first.ask_point is None and first.current_point_id == "p1"
    assert _status(first, "p1") == "hinted"
    second = plan_review_turn(first.points, "p1", ReviewTurnInput(False, []), wrap_up_offered=False)
    assert second.explain_point is not None and second.explain_point["id"] == "p1"
    assert _status(second, "p1") == "not_explained"
    assert second.ask_point is not None and second.ask_point["id"] == "p2"


def test_answer_after_hint_counts_as_explained_with_hint() -> None:
    pts = _set(_queued(["p1", "p2"]), "p1", "hinted")
    plan = plan_review_turn(pts, "p1", ReviewTurnInput(True, []), wrap_up_offered=False)
    assert _status(plan, "p1") == "explained_with_hint"
    assert plan.hint_point is None and plan.explain_point is None
    assert plan.ask_point is not None and plan.ask_point["id"] == "p2"


def test_explained_current_point_without_hint_is_explained() -> None:
    plan = plan_review_turn(_queued(["p1", "p2"]), "p1", ReviewTurnInput(True, []), wrap_up_offered=False)
    assert _status(plan, "p1") == "explained"


def test_other_points_explained_in_passing_are_skipped() -> None:
    plan = plan_review_turn(_queued(["p1", "p2", "p3"]), "p1", ReviewTurnInput(True, ["p2"]), wrap_up_offered=False)
    assert _status(plan, "p2") == "explained"
    assert plan.ask_point is not None and plan.ask_point["id"] == "p3"


def test_last_point_answered_offers_wrap_up_once() -> None:
    pts = _queued(["p1"])
    plan = plan_review_turn(pts, "p1", ReviewTurnInput(True, []), wrap_up_offered=False)
    assert plan.wrap_up is True
    assert plan.ask_point is None and plan.current_point_id is None


def test_after_wrap_up_offered_continues_with_unqueued_points() -> None:
    pts = initial_review_points([_point(f"p{i}") for i in range(1, 7)])
    pts = [{**p, "queued": i < 4} for i, p in enumerate(pts)]
    for pid in ("p1", "p2", "p3", "p4"):
        pts = _set(pts, pid, "explained")
    plan = plan_review_turn(pts, "p4", ReviewTurnInput(True, []), wrap_up_offered=True)
    assert plan.wrap_up is False
    assert plan.ask_point is not None and plan.ask_point["id"] == "p5"
    assert [p["id"] for p in plan.points if p["queued"]] == ["p1", "p2", "p3", "p4", "p5"]
    assert plan.current_point_id == "p5"


def test_no_points_left_returns_free_turn() -> None:
    pts = _set(_queued(["p1"]), "p1", "explained")
    plan = plan_review_turn(pts, "p1", ReviewTurnInput(True, []), wrap_up_offered=True)
    assert plan.hint_point is None and plan.explain_point is None and plan.ask_point is None
    assert plan.wrap_up is False and plan.current_point_id is None


def test_failed_analysis_changes_nothing_and_re_asks_current() -> None:
    pts = _queued(["p1", "p2"])
    plan = plan_review_turn(pts, "p1", None, wrap_up_offered=False)
    assert plan.points == pts
    assert plan.ask_point is not None and plan.ask_point["id"] == "p1"
    assert plan.current_point_id == "p1" and plan.hint_point is None and plan.wrap_up is False


def test_failed_analysis_without_current_point_asks_nothing() -> None:
    plan = plan_review_turn(initial_review_points([_point("p1")]), None, None, wrap_up_offered=False)
    assert plan.ask_point is None and plan.current_point_id is None


def test_review_results_maps_statuses() -> None:
    pts = initial_review_points([_point(f"p{i}") for i in range(1, 8)])
    pts = [{**p, "queued": i < 6} for i, p in enumerate(pts)]
    for pid, status in [("p1", "explained"), ("p2", "explained_with_hint"), ("p3", "not_explained"), ("p4", "hinted")]:
        pts = _set(pts, pid, status)
    results = review_results(pts)
    assert [(r["point_id"], r["status"]) for r in results] == [
        ("p1", "explained"),
        ("p2", "explained_with_hint"),
        ("p3", "not_explained"),
        ("p4", "not_explained"),
        ("p5", "not_asked"),
        ("p6", "not_asked"),
    ]
    assert results[0] == {
        "point_id": "p1",
        "point": "要点 p1",
        "question": "質問 p1",
        "status": "explained",
        "aspect_id": None,
    }


def test_review_results_handles_none() -> None:
    assert review_results(None) == []


def test_answer_after_declined_wrap_up_continues_one_point_at_a_time() -> None:
    pts = initial_review_points([_point(f"p{i}") for i in range(1, 7)])
    pts = [{**p, "queued": i < 4} for i, p in enumerate(pts)]
    for pid in ("p1", "p2", "p3", "p4"):
        pts = _set(pts, pid, "explained")
    plan = plan_review_turn(pts, None, ReviewTurnInput(False, []), wrap_up_offered=True)
    assert plan.ask_point is not None and plan.ask_point["id"] == "p5"
    assert [p["id"] for p in plan.points if p["queued"]] == ["p1", "p2", "p3", "p4", "p5"]
