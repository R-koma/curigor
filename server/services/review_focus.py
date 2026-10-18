from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from graph.aspect_map import iter_aspects


@dataclass(frozen=True)
class ReviewFocus:
    prior_improvements: str | None
    priority_aspects: list[str] = field(default_factory=list)


def build_review_focus(
    latest_feedback: dict[str, Any] | None,
    aspect_map: dict[str, Any] | None,
    memo_aspect_ids: Sequence[str] = (),
) -> ReviewFocus:
    improvements = ((latest_feedback or {}).get("improvements") or "").strip()
    if aspect_map is None:
        return ReviewFocus(improvements or None)

    memo_ids = set(memo_aspect_ids)
    priority = [ref.name for ref in iter_aspects(aspect_map) if ref.id in memo_ids]
    return ReviewFocus(improvements or None, priority)
