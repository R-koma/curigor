from typing import Any

from core.database import get_pool
from graph.explore import merge_terms, overview_aspects
from graph.nodes._explore_llm import extract_terms, summarize_answers
from graph.state import LearningState
from repositories import study_memo_repository


def _answered_questions(state: LearningState) -> list[tuple[str, str]]:
    answers = {m.id: str(m.content) for m in state["messages"] if m.type == "ai" and m.id}
    return [
        (q["question"], answers[q["answer_message_id"]])
        for q in state.get("explore_questions") or []
        if q["answer_message_id"] in answers
    ]


async def generate_study_memo(state: LearningState) -> dict[str, Any]:
    depth_map = state.get("depth_map")
    if not depth_map:
        return {}
    terms = list(state.get("explore_terms") or [])
    last_ai = next((m for m in reversed(state["messages"]) if m.type == "ai"), None)
    if last_ai is not None:
        terms = merge_terms(terms, await extract_terms(str(last_ai.content)))
    pairs = _answered_questions(state)
    summaries = await summarize_answers(pairs)
    overview = overview_aspects(depth_map, state.get("explore_overview") or {}, state.get("explained_aspects") or [])

    pool = await get_pool()
    async with pool.acquire() as conn:
        await study_memo_repository.insert(
            conn,
            user_id=state["user_id"],
            dialogue_session_id=state["dialogue_session_id"],
            topic=state["topic"],
            source=state.get("learning_source") or "",
            overview=[dict(a) for a in overview],
            glossary=[{"term": t["term"], "reading": t["reading"], "meaning": t["meaning"]} for t in terms],
            questions=[{"question": q, "answer": summaries.get(i, "")} for i, (q, _) in enumerate(pairs)],
            depth_map=dict(depth_map),
        )
    return {}


__all__ = ["generate_study_memo"]
