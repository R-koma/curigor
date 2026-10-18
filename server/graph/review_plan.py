from collections.abc import Sequence
from typing import Any, Literal, TypedDict

from graph.aspect_map import aspect_names_by_id
from graph.output_schemas import ReviewPlanPointDraft, ReviewPointSource

ReviewResultStatus = Literal["explained", "explained_with_hint", "not_explained", "not_asked"]

MAX_PLAN_POINTS = 10

_SOURCE_RANK: dict[str, int] = {
    "carryover": 0,
    "improvement": 1,
    "aspect_gap": 2,
    "general": 2,
    "ambiguous": 3,
    "ai_supplement": 3,
    "covered": 4,
}


class ReviewPlanPoint(TypedDict):
    id: str
    point: str
    question: str
    expected: list[str]
    source: ReviewPointSource
    aspect_id: str | None
    in_note: bool


class CarryoverPoint(TypedDict):
    key: str
    point: str
    question: str
    aspect_id: str | None
    expected: list[str]


class ReviewResult(TypedDict):
    point_id: str
    point: str
    question: str
    status: ReviewResultStatus
    aspect_id: str | None


def carryover_points(
    previous_plan: list[ReviewPlanPoint] | None, latest_results: list[ReviewResult] | None
) -> list[CarryoverPoint]:
    results = latest_results or []
    expected_by_point = {p["point"]: p["expected"] for p in previous_plan or []}
    result_points = {r["point"] for r in results}
    candidates: list[tuple[str, str, str | None]] = [
        (r["point"], r["question"], r["aspect_id"]) for r in results if r["status"] in ("not_explained", "not_asked")
    ]
    candidates += [
        (p["point"], p["question"], p["aspect_id"])
        for p in previous_plan or []
        if p["source"] == "carryover" and p["point"] not in result_points
    ]
    seen: set[str] = set()
    carried: list[CarryoverPoint] = []
    for point, question, aspect_id in candidates:
        if point in seen:
            continue
        seen.add(point)
        carried.append(
            {
                "key": f"c{len(carried) + 1}",
                "point": point,
                "question": question,
                "aspect_id": aspect_id,
                "expected": list(expected_by_point.get(point, [])),
            }
        )
    return carried


def sanitize_plan_points(
    drafts: list[ReviewPlanPointDraft], aspect_map: dict[str, Any] | None, carryover: list[CarryoverPoint]
) -> list[ReviewPlanPoint]:
    known = aspect_names_by_id(aspect_map)
    by_key = {c["key"]: c for c in carryover}
    used_keys: set[str] = set()
    kept: list[ReviewPlanPoint] = []
    for draft in drafts:
        aspect_id = draft.aspect_id.strip()
        carried = by_key.get(draft.carryover_key.strip())
        if carried is not None and carried["key"] not in used_keys:
            used_keys.add(carried["key"])
            kept.append(
                {
                    "id": "",
                    "point": carried["point"],
                    "question": draft.question,
                    "expected": draft.expected or carried["expected"],
                    "source": "carryover",
                    "aspect_id": aspect_id if aspect_id in known else carried["aspect_id"],
                    "in_note": draft.in_note,
                }
            )
            continue
        if not draft.expected:
            continue
        kept.append(
            {
                "id": "",
                "point": draft.point,
                "question": draft.question,
                "expected": draft.expected,
                "source": "general" if draft.source == "carryover" else draft.source,
                "aspect_id": aspect_id if aspect_id in known else None,
                "in_note": draft.in_note,
            }
        )
    for carried in carryover:
        if carried["key"] in used_keys:
            continue
        kept.append(
            {
                "id": "",
                "point": carried["point"],
                "question": carried["question"],
                "expected": carried["expected"],
                "source": "carryover",
                "aspect_id": carried["aspect_id"] if carried["aspect_id"] in known else None,
                "in_note": True,
            }
        )
    limit = max(0, MAX_PLAN_POINTS - len(carryover))
    result: list[ReviewPlanPoint] = []
    others = 0
    for point in kept:
        if point["source"] != "carryover":
            if others >= limit:
                continue
            others += 1
        result.append(point)
    for index, point in enumerate(result, start=1):
        point["id"] = f"p{index}"
    return result


def _matches_focus(aspect_id: str | None, focus_aspect_ids: list[str]) -> bool:
    if not aspect_id:
        return False
    return any(aspect_id == f or aspect_id.startswith(f + "-") for f in focus_aspect_ids)


def order_review_points(
    points: list[ReviewPlanPoint],
    focus_aspect_ids: list[str] | None,
    priority_aspect_ids: Sequence[str] = (),
) -> list[ReviewPlanPoint]:
    focus = focus_aspect_ids or []
    priority = list(priority_aspect_ids)
    ranked = sorted(
        enumerate(points),
        key=lambda item: (
            bool(focus) and not _matches_focus(item[1]["aspect_id"], focus),
            bool(priority) and not _matches_focus(item[1]["aspect_id"], priority),
            _SOURCE_RANK[item[1]["source"]],
            item[0],
        ),
    )
    return [point for _, point in ranked]
