from collections.abc import Mapping
from typing import Any

from graph.state import EndConfirmationStatus

_EXPLAINED_MAP_STAGES = frozenset({"defined", "reasoned", "applied"})
_EXPLAINED_DEPTHS = frozenset({"defined", "exemplified", "applied"})


def has_learner_content(values: Mapping[str, Any]) -> bool:
    session_type = values.get("session_type")
    if session_type == "synthesis":
        return True
    if session_type == "review":
        return review_answered(values)
    if values.get("depth_map"):
        return any(c["reached_stage"] in _EXPLAINED_MAP_STAGES for c in values.get("map_covered") or [])
    return any(c["reached_depth"] in _EXPLAINED_DEPTHS for c in values.get("covered_aspects") or [])


def review_answered(values: Mapping[str, Any]) -> bool:
    if "review_answered" in values:
        return bool(values["review_answered"])
    humans = [m for m in values.get("messages") or [] if getattr(m, "type", "") == "human"]
    return len(humans) > 1


def end_confirmation_after(
    previous: EndConfirmationStatus | None, *, wants_to_end: bool, offer: bool
) -> EndConfirmationStatus | None:
    if wants_to_end:
        return "confirmed" if previous == "offered" else "offered"
    return "offered" if offer else None
