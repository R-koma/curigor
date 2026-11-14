"""インプットセッションの決定的な処理（用語のマージ・観点の順番）。"""

import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

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


def merge_side_terms(
    glossary: Sequence[Mapping[str, Any]], drafts: Sequence[ExploreTermDraft]
) -> list[dict[str, Any]]:
    merged = [dict(t) for t in glossary]
    positions = {_normalize(t["term"]): i for i, t in enumerate(merged)}
    for draft in drafts:
        term = draft.term.strip()
        key = _normalize(term)
        if not key or len(term) > MAX_TERM_LENGTH:
            continue
        reading = draft.reading.strip()[:MAX_READING_LENGTH]
        entry = {
            "term": term,
            "reading": reading,
            "meaning": draft.meaning.strip()[:MAX_MEANING_LENGTH],
            "from_side": True,
        }
        if key in positions:
            existing = merged[positions[key]]
            merged[positions[key]] = {**entry, "term": existing["term"], "reading": reading or existing["reading"]}
        else:
            positions[key] = len(merged)
            merged.append(entry)
    return merged


def side_threads_in_order(threads: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    children: dict[UUID | None, list[Mapping[str, Any]]] = {}
    ids = {t["id"] for t in threads}
    for thread in threads:
        parent = thread["parent_id"] if thread["parent_id"] in ids else None
        children.setdefault(parent, []).append(thread)
    ordered: list[Mapping[str, Any]] = []

    def visit(parent: UUID | None) -> None:
        for thread in children.get(parent, []):
            ordered.append(thread)
            visit(thread["id"])

    visit(None)
    return ordered


def side_memo_questions(
    ordered: Sequence[Mapping[str, Any]], questions: Mapping[UUID, tuple[str, str]], *, start: int
) -> list[dict[str, Any]]:
    by_id = {t["id"]: t for t in ordered}
    index_of: dict[UUID, int] = {}
    result: list[dict[str, Any]] = []
    for thread in ordered:
        if thread["id"] not in questions:
            continue
        parent_index = None
        ancestor = by_id.get(thread["parent_id"]) if thread["parent_id"] is not None else None
        while ancestor is not None:
            if ancestor["id"] in index_of:
                parent_index = index_of[ancestor["id"]]
                break
            ancestor = by_id.get(ancestor["parent_id"]) if ancestor["parent_id"] is not None else None
        question, answer = questions[thread["id"]]
        index_of[thread["id"]] = start + len(result)
        result.append(
            {
                "question": question,
                "answer": answer,
                "quote": thread["quote"],
                "parent_index": parent_index,
                "from_side": True,
            }
        )
    return result


def place_child_questions(
    overview: Sequence[Mapping[str, Any]], questions: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    placed = [{**a, "question_indices": list(a["question_indices"])} for a in overview]
    for index, question in enumerate(questions):
        parent = question.get("parent_index")
        if parent is None:
            continue
        for aspect in placed:
            indices: list[int] = aspect["question_indices"]
            if parent in indices:
                position = indices.index(parent) + 1
                while position < len(indices) and _descends(questions, indices[position], parent):
                    position += 1
                indices.insert(position, index)
                break
    return placed


def _descends(questions: Sequence[Mapping[str, Any]], index: int, ancestor: int) -> bool:
    current = questions[index].get("parent_index")
    while current is not None:
        if current == ancestor:
            return True
        current = questions[current].get("parent_index")
    return False
