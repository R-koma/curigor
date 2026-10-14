from typing import Any

from core.database import get_pool
from graph.explore import EXPLORE_PRIOR_KNOWLEDGE, merge_terms, ordered_aspects
from graph.nodes._depth_map_generation import generate_depth_map
from graph.nodes._explore_llm import draft_teachback_map, extract_terms, summarize_answers
from graph.state import DepthMapState, ExploreTerm, LearningState
from repositories import study_memo_repository


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


async def generate_study_memo(state: LearningState) -> dict[str, Any]:
    topic = state["topic"]
    terms = list(state.get("explore_terms") or [])
    last_ai = next((m for m in reversed(state["messages"]) if m.type == "ai"), None)
    if last_ai is not None:
        terms = merge_terms(terms, await extract_terms(str(last_ai.content)))
    pairs = _answered_questions(state)
    summaries = await summarize_answers(pairs)
    depth_map = await _teachback_map(topic, pairs, terms)
    overview = [
        {"aspect_id": a["id"], "name": a["name"], "summary": "", "is_core": a["is_core"]}
        for a in ordered_aspects(depth_map)
    ]

    pool = await get_pool()
    async with pool.acquire() as conn:
        await study_memo_repository.insert(
            conn,
            user_id=state["user_id"],
            dialogue_session_id=state["dialogue_session_id"],
            topic=topic,
            source=state.get("learning_source") or "",
            overview=overview,
            glossary=[{"term": t["term"], "reading": t["reading"], "meaning": t["meaning"]} for t in terms],
            questions=[{"question": q, "answer": summaries.get(i, "")} for i, (q, _) in enumerate(pairs)],
            depth_map=dict(depth_map),
        )
    return {}


__all__ = ["generate_study_memo"]
