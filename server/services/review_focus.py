import json
from dataclasses import dataclass
from typing import Any

from graph.aspect_map import iter_aspects


@dataclass(frozen=True)
class ReviewFocus:
    prior_improvements: str | None
    focus_aspects: list[str]


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
) -> ReviewFocus:
    improvements = ((latest_feedback or {}).get("improvements") or "").strip()
    if focus_aspect_ids is None or aspect_map is None:
        return ReviewFocus(improvements or None, [])

    known = {ref.id: ref.name for ref in iter_aspects(aspect_map)}
    selected = [aspect_id for aspect_id in known if aspect_id in set(focus_aspect_ids)]
    focus_names = [known[aspect_id] for aspect_id in selected]

    items = _improvement_items(latest_feedback) if latest_feedback else None
    if items is None:
        return ReviewFocus(improvements or None, focus_names)

    kept = [
        str(item["text"]) for item in items if item.get("aspect_id") not in known or item.get("aspect_id") in selected
    ]
    return ReviewFocus("\n".join(kept) or None, focus_names)
