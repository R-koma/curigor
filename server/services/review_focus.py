import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from graph.aspect_map import iter_aspects


@dataclass(frozen=True)
class ReviewFocus:
    prior_improvements: str | None
    focus_aspects: list[str]
    priority_aspects: list[str] = field(default_factory=list)


def _improvement_items(feedback: dict[str, Any]) -> list[dict[str, Any]] | None:
    raw = feedback.get("improvement_items")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw if isinstance(raw, list) else None


def build_review_focus(
    latest_feedback: dict[str, Any] | None,
    aspect_map: dict[str, Any] | None,
    focus_aspect_ids: list[str] | None,
    memo_aspect_ids: Sequence[str] = (),
) -> ReviewFocus:
    improvements = ((latest_feedback or {}).get("improvements") or "").strip()
    if aspect_map is None:
        return ReviewFocus(improvements or None, [])

    known = {ref.id: ref.name for ref in iter_aspects(aspect_map)}
    priority = [
        name
        for aspect_id, name in known.items()
        if aspect_id in set(memo_aspect_ids) and (focus_aspect_ids is None or aspect_id in focus_aspect_ids)
    ]
    if focus_aspect_ids is None:
        return ReviewFocus(improvements or None, [], priority)

    selected = [aspect_id for aspect_id in known if aspect_id in set(focus_aspect_ids)]
    focus_names = [known[aspect_id] for aspect_id in selected]

    items = _improvement_items(latest_feedback) if latest_feedback else None
    if items is None:
        return ReviewFocus(improvements or None, focus_names, priority)

    kept = [
        str(item["text"]) for item in items if item.get("aspect_id") not in known or item.get("aspect_id") in selected
    ]
    return ReviewFocus("\n".join(kept) or None, focus_names, priority)
