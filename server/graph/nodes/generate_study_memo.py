import asyncio
import logging
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from core.database import get_pool
from graph.explore import (
    EXPLORE_PRIOR_KNOWLEDGE,
    build_overview,
    merge_side_terms,
    merge_terms,
    ordered_aspects,
    place_child_questions,
    side_memo_questions,
    side_threads_in_order,
)
from graph.nodes._depth_map_generation import generate_depth_map
from graph.nodes._explore_llm import (
    SideQuestionDigest,
    digest_side_questions,
    draft_teachback_map,
    extract_terms,
    organize_memo,
    summarize_answers,
)
from graph.output_schemas import ExploreMemoAspect, ExploreMemoOrganization
from graph.state import DepthMapState, ExploreTerm, LearningState
from repositories import side_question_repository, study_memo_repository
from repositories.study_memo_repository import MemoOrigin

logger = logging.getLogger(__name__)


def _answered_questions(state: LearningState) -> list[tuple[str, str]]:
    answers = {m.id: str(m.content) for m in state["messages"] if m.type == "ai" and m.id}
    return [
        (q["question"], answers[q["answer_message_id"]])
        for q in state.get("explore_questions") or []
        if q["answer_message_id"] in answers
    ]


async def _teachback_map(topic: str, pairs: list[tuple[str, str]], terms: list[ExploreTerm]) -> DepthMapState:
    depth_map = await draft_teachback_map(topic, pairs, terms)
    if depth_map is None:
        depth_map = await generate_depth_map(
            topic=topic, purpose="", source="", prior_knowledge=EXPLORE_PRIOR_KNOWLEDGE
        )
    return depth_map or {"topic": topic, "aspects": []}


def _side_pairs(threads: list[Mapping[str, Any]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for thread in threads:
        messages = thread["messages"]
        for asked, answered in zip(messages, messages[1:], strict=False):
            if asked["role"] == "user" and answered["role"] == "assistant":
                pairs.append((f"「{thread['quote']}」について: {asked['content']}", answered["content"]))
    return pairs


async def _terms_and_map(
    state: LearningState, pairs: list[tuple[str, str]], threads: list[Mapping[str, Any]]
) -> tuple[list[ExploreTerm], DepthMapState]:
    terms = list(state.get("explore_terms") or [])
    last_ai = next((m for m in reversed(state["messages"]) if m.type == "ai"), None)
    if last_ai is not None:
        terms = merge_terms(terms, await extract_terms(state["topic"], str(last_ai.content)))
    return terms, await _teachback_map(state["topic"], [*pairs, *_side_pairs(threads)], terms)


async def _digest(topic: str, threads: list[Mapping[str, Any]]) -> dict[UUID, SideQuestionDigest]:
    return await digest_side_questions(topic, threads) if threads else {}


async def _side_threads(state: LearningState) -> list[Mapping[str, Any]]:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            threads = await side_question_repository.find_threads(conn, UUID(str(state["dialogue_session_id"])))
    except Exception:
        logger.exception("Failed to read side questions for session %s", state.get("dialogue_session_id"))
        return []
    return side_threads_in_order(threads)


def _organized_for_memo(
    organization: ExploreMemoOrganization | None, memo_indices: list[int]
) -> ExploreMemoOrganization | None:
    if organization is None:
        return None
    return organization.model_copy(
        update={
            "aspects": [
                ExploreMemoAspect(
                    aspect_id=a.aspect_id,
                    question_indices=[memo_indices[i] for i in a.question_indices if 0 <= i < len(memo_indices)],
                    term_indices=a.term_indices,
                )
                for a in organization.aspects
            ]
        }
    )


async def generate_study_memo(state: LearningState) -> dict[str, Any]:
    topic = state["topic"]
    pairs = _answered_questions(state)
    threads = await _side_threads(state)
    (terms, depth_map), summaries, digests = await asyncio.gather(
        _terms_and_map(state, pairs, threads), summarize_answers(pairs), _digest(topic, threads)
    )
    questions: list[dict[str, Any]] = [
        {"question": q, "answer": summaries.get(i, "")} for i, (q, _) in enumerate(pairs)
    ]
    questions += side_memo_questions(
        threads, {k: (d.question, d.answer) for k, d in digests.items() if d.question}, start=len(questions)
    )
    glossary = merge_side_terms(
        [{"term": t["term"], "reading": t["reading"], "meaning": t["meaning"]} for t in terms],
        [d.term for t in threads if (d := digests.get(t["id"])) is not None and d.term is not None],
    )
    top_level = [i for i, q in enumerate(questions) if q.get("parent_index") is None]
    organize_pairs = [
        pairs[i] if i < len(pairs) else (questions[i]["question"], questions[i]["answer"]) for i in top_level
    ]
    organize_terms: list[ExploreTerm] = [
        {"term": t["term"], "reading": t["reading"], "meaning": t["meaning"]} for t in glossary
    ]
    aspects = ordered_aspects(depth_map)
    organization = (
        await organize_memo(topic, aspects, organize_pairs, organize_terms)
        if aspects and (organize_pairs or organize_terms)
        else None
    )
    overview = build_overview(
        aspects,
        _organized_for_memo(organization, top_level),
        question_count=len(questions),
        term_count=len(glossary),
    )
    overview = place_child_questions(overview, questions)

    gap = state.get("explore_gap")
    origin: MemoOrigin | None = (
        {
            "note_id": gap["note_id"],
            "feedback_id": gap["feedback_id"],
            "improvement_index": gap["improvement_index"],
            "improvement": gap["improvement"],
            "aspect_id": gap.get("aspect_id"),
        }
        if gap
        else None
    )

    pool = await get_pool()
    async with pool.acquire() as conn:
        await study_memo_repository.insert(
            conn,
            user_id=state["user_id"],
            dialogue_session_id=state["dialogue_session_id"],
            topic=topic,
            source=state.get("learning_source") or "",
            summary=organization.summary.strip() if organization else "",
            overview=overview,
            glossary=glossary,
            questions=questions,
            depth_map=dict(depth_map),
            origin=origin,
        )
    return {}


__all__ = ["generate_study_memo"]
