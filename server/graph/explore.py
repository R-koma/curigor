"""インプットセッションの決定的な処理（用語のマージ・観点の順番・全体像）。"""

import unicodedata
from collections.abc import Mapping, Sequence

from graph.output_schemas import ExploreTermDraft
from graph.state import DepthMapAspectState, DepthMapState, ExploreOverviewAspect, ExploreTerm

EXPLORE_PRIOR_KNOWLEDGE = "ほとんど知らない（初めて学ぶ）"
NO_MATERIAL_LABEL = "教材なし"

MAX_TERM_LENGTH = 40
MAX_READING_LENGTH = 60
MAX_MEANING_LENGTH = 120


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip().casefold()


def merge_terms(existing: Sequence[ExploreTerm], drafts: Sequence[ExploreTermDraft]) -> list[ExploreTerm]:
    merged = list(existing)
    seen = {_normalize(t["term"]) for t in merged}
    for draft in drafts:
        term = draft.term.strip()[:MAX_TERM_LENGTH]
        key = _normalize(term)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(
            {
                "term": term,
                "reading": draft.reading.strip()[:MAX_READING_LENGTH],
                "meaning": draft.meaning.strip()[:MAX_MEANING_LENGTH],
            }
        )
    return merged


def ordered_aspects(depth_map: DepthMapState) -> list[DepthMapAspectState]:
    return sorted(depth_map["aspects"], key=lambda a: not a["is_core"])


def next_aspect_id(depth_map: DepthMapState, explained: Sequence[str]) -> str | None:
    done = set(explained)
    return next((a["id"] for a in ordered_aspects(depth_map) if a["id"] not in done), None)


def known_aspect_id(reference: str, depth_map: DepthMapState) -> str | None:
    key = _normalize(reference)
    if not key:
        return None
    for aspect in depth_map["aspects"]:
        if key in (_normalize(aspect["id"]), _normalize(aspect["name"])):
            return aspect["id"]
    return None


def all_core_explained(depth_map: DepthMapState, explained: Sequence[str]) -> bool:
    cores = [a["id"] for a in depth_map["aspects"] if a["is_core"]]
    return bool(cores) and set(cores) <= set(explained)


def overview_aspects(
    depth_map: DepthMapState, summaries: Mapping[str, str], explained: Sequence[str]
) -> list[ExploreOverviewAspect]:
    done = set(explained)
    return [
        {
            "aspect_id": a["id"],
            "name": a["name"],
            "summary": summaries.get(a["id"], ""),
            "is_core": a["is_core"],
            "explained": a["id"] in done,
        }
        for a in ordered_aspects(depth_map)
    ]


def overview_text(topic: str, aspects: Sequence[ExploreOverviewAspect]) -> str:
    lines = [
        f"{i}. {a['name']}: {a['summary']}" if a["summary"] else f"{i}. {a['name']}" for i, a in enumerate(aspects, 1)
    ]
    return (
        f"「{topic}」は、大きく次の{len(aspects)}つに分けられます。\n"
        + "\n".join(lines)
        + "\n\nどこから始めますか？迷ったら「最初から」と送ってください。"
    )
