"""インプットセッションの決定的な処理（用語のマージ・観点の順番）。"""

import unicodedata
from collections.abc import Sequence

from graph.output_schemas import ExploreTermDraft
from graph.state import DepthMapAspectState, DepthMapState, ExploreTerm

EXPLORE_PRIOR_KNOWLEDGE = "ほとんど知らない（初めて学ぶ）"

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
