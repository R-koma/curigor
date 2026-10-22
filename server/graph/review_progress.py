from dataclasses import dataclass
from typing import Literal

from graph.review_plan import ReviewPlanPoint, ReviewResult, ReviewResultStatus

REVIEW_ASK_LIMIT = 4

ReviewPointStatus = Literal[
    "pending", "hinted", "explained", "explained_with_hint", "explained_after_note", "not_explained"
]


class ReviewPointState(ReviewPlanPoint):
    status: ReviewPointStatus
    queued: bool


@dataclass(frozen=True)
class ReviewTurnInput:
    current_point_explained: bool
    explained_point_ids: list[str]
    viewed_note: bool = False


@dataclass(frozen=True)
class ReviewTurnPlan:
    points: list[ReviewPointState]
    current_point_id: str | None
    hint_point: ReviewPointState | None
    explain_point: ReviewPointState | None
    ask_point: ReviewPointState | None
    wrap_up: bool


def expected_text(point: ReviewPointState) -> str:
    return "、".join(point["expected"])


def initial_review_points(ordered: list[ReviewPlanPoint]) -> list[ReviewPointState]:
    return [ReviewPointState(**point, status="pending", queued=False) for point in ordered]


def _find(points: list[ReviewPointState], point_id: str | None) -> ReviewPointState | None:
    if point_id is None:
        return None
    return next((p for p in points if p["id"] == point_id), None)


def _with(points: list[ReviewPointState], point_id: str, **changes: object) -> list[ReviewPointState]:
    return [ReviewPointState(**{**p, **changes}) if p["id"] == point_id else p for p in points]  # type: ignore[typeddict-item]


def plan_review_turn(
    points: list[ReviewPointState],
    current_point_id: str | None,
    turn: ReviewTurnInput | None,
    *,
    wrap_up_offered: bool,
) -> ReviewTurnPlan:
    points = [ReviewPointState(**p) for p in points]
    if turn is None:
        return ReviewTurnPlan(points, current_point_id, None, None, _find(points, current_point_id), False)

    for point_id in turn.explained_point_ids:
        target = _find(points, point_id)
        if point_id != current_point_id and target is not None and target["status"] == "pending":
            points = _with(points, point_id, status="explained_after_note" if turn.viewed_note else "explained")

    if current_point_id is None and not any(p["queued"] for p in points):
        pending_ids = [p["id"] for p in points if p["status"] == "pending"][:REVIEW_ASK_LIMIT]
        for point_id in pending_ids:
            points = _with(points, point_id, queued=True)

    explain_point: ReviewPointState | None = None
    current = _find(points, current_point_id)
    if current is not None:
        if turn.current_point_explained:
            if turn.viewed_note and current["status"] in ("pending", "hinted"):
                points = _with(points, current["id"], status="explained_after_note")
            elif current["status"] == "pending":
                points = _with(points, current["id"], status="explained")
            elif current["status"] == "hinted":
                points = _with(points, current["id"], status="explained_with_hint")
        elif current["status"] == "pending":
            points = _with(points, current["id"], status="hinted")
            return ReviewTurnPlan(points, current_point_id, _find(points, current_point_id), None, None, False)
        elif current["status"] == "hinted":
            points = _with(points, current["id"], status="not_explained")
            explain_point = _find(points, current["id"])

    ask_point = next((p for p in points if p["queued"] and p["status"] == "pending"), None)
    wrap_up = False
    if ask_point is None:
        if not wrap_up_offered:
            wrap_up = True
        else:
            extra = next((p for p in points if not p["queued"] and p["status"] == "pending"), None)
            if extra is not None:
                points = _with(points, extra["id"], queued=True)
                ask_point = _find(points, extra["id"])

    return ReviewTurnPlan(
        points, ask_point["id"] if ask_point is not None else None, None, explain_point, ask_point, wrap_up
    )


def review_results(points: list[ReviewPointState] | None) -> list[ReviewResult]:
    results: list[ReviewResult] = []
    for p in points or []:
        status: ReviewResultStatus
        if p["status"] in ("explained", "explained_with_hint", "explained_after_note", "not_explained"):
            status = p["status"]
        elif p["status"] == "hinted":
            status = "not_explained"
        elif p["queued"]:
            status = "not_asked"
        else:
            continue
        results.append(
            {
                "point_id": p["id"],
                "point": p["point"],
                "question": p["question"],
                "status": status,
                "aspect_id": p["aspect_id"],
            }
        )
    return results
