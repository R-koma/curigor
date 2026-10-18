"""インプットセッションの決定的な処理（用語のマージ・観点の順番）。"""

import unicodedata
from collections.abc import Sequence
from typing import Any

from graph.output_schemas import ExploreMemoOrganization, ExploreTermDraft
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
        term = draft.term.strip()
        key = _normalize(term)
        if not key or key in seen or len(term) > MAX_TERM_LENGTH:
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


def _claim(indices: Sequence[int], count: int, claimed: set[int]) -> list[int]:
    own: list[int] = []
    for index in indices:
        if 0 <= index < count and index not in claimed:
            claimed.add(index)
            own.append(index)
    return own


def build_overview(
    aspects: Sequence[DepthMapAspectState],
    organization: ExploreMemoOrganization | None,
    *,
    question_count: int,
    term_count: int,
) -> list[dict[str, Any]]:
    by_id = {a.aspect_id: a for a in organization.aspects} if organization else {}
    claimed_questions: set[int] = set()
    claimed_terms: set[int] = set()
    overview: list[dict[str, Any]] = []
    for aspect in sorted(aspects, key=lambda a: not a["is_core"]):
        assigned = by_id.get(aspect["id"])
        overview.append(
            {
                "aspect_id": aspect["id"],
                "name": aspect["name"],
                "is_core": aspect["is_core"],
                "question_indices": _claim(assigned.question_indices, question_count, claimed_questions)
                if assigned
                else [],
                "term_indices": _claim(assigned.term_indices, term_count, claimed_terms) if assigned else [],
            }
        )
    return overview
