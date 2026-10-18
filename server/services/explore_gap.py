import json
import re
from typing import Any

from graph.aspect_map import iter_aspects, parse_aspect_map
from graph.state import ExploreGap
from schemas.websocket_message import ExploreSource

_LEADING_MARK = re.compile(r"^[\s・\-*]+")


def _improvement_items(feedback: dict[str, Any]) -> list[dict[str, Any]] | None:
    raw = feedback.get("improvement_items")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw if isinstance(raw, list) else None


def _split_legacy(improvements: str) -> list[str]:
    lines = (_LEADING_MARK.sub("", line).strip() for line in improvements.split("\n"))
    return [line for line in lines if line]


def resolve_gap(note: dict[str, Any], feedbacks: list[dict[str, Any]], source: ExploreSource) -> ExploreGap | None:
    if not feedbacks:
        return None
    latest = feedbacks[-1]
    if str(latest["id"]) != str(source.feedback_id):
        return None

    index = source.improvement_index
    aspect_id: str | None = None
    items = _improvement_items(latest)
    if items is not None:
        if index >= len(items):
            return None
        text = items[index].get("text") if isinstance(items[index], dict) else None
        if not isinstance(text, str):
            return None
        improvement = text
        raw_aspect_id = items[index].get("aspect_id")
        aspect_id = str(raw_aspect_id) if raw_aspect_id else None
    else:
        legacy = _split_legacy(latest.get("improvements") or "")
        if index >= len(legacy):
            return None
        improvement = legacy[index]

    gap = ExploreGap(
        note_id=str(source.note_id),
        feedback_id=str(source.feedback_id),
        improvement_index=index,
        improvement=improvement,
        note_content=str(note["content"]),
    )
    aspect_map = parse_aspect_map(note.get("aspect_map"))
    if aspect_id is not None and aspect_map is not None:
        for ref in iter_aspects(aspect_map):
            if ref.id == aspect_id:
                gap["aspect_id"] = ref.id
                gap["aspect_name"] = ref.name
                break
    return gap


def gap_opening_utterance(gap: ExploreGap) -> str:
    return f"改善点「{gap['improvement']}」を理解したい"
