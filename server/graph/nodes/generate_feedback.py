import asyncio
from typing import Any

from core.database import get_pool
from graph.aspect_map import feedback_insert_fields
from graph.nodes._aspect_map_generation import conversation_text_for_aspect_map, generate_aspect_map
from graph.nodes._feedback_assessment import (
    analyze_dialogue,
    format_conversation_history,
    format_note_text,
    score_feedback,
)
from graph.state import LearningState
from repositories import feedback_repository, note_repository, review_schedule_repository
from services.review_scheduler import calculate_next_review


async def generate_feedback(state: LearningState) -> dict[str, Any]:
    """会話履歴を分析し、理解度評価を生成してDBに保存"""

    pool = await get_pool()
    topic = state["topic"]

    note_id = state["note_id"]
    analysis, aspect_map_model = await asyncio.gather(
        analyze_dialogue(topic, format_conversation_history(state["messages"])),
        generate_aspect_map(conversation_text_for_aspect_map(state["messages"]), note_id),
    )
    aspect_map = aspect_map_model.model_dump() if aspect_map_model is not None else None

    async with pool.acquire() as conn:
        if aspect_map_model is not None:
            await note_repository.update_aspect_map(conn, note_id, aspect_map_model.model_dump_json())
        note = await note_repository.find_by_id(conn, note_id, state["user_id"])
        if not note:
            raise RuntimeError(f"Note {note_id} not found")

        feedback_data = await score_feedback(
            topic, analysis, aspect_map, format_note_text(note["topic"], note["content"])
        )

        await feedback_repository.insert(
            conn=conn,
            note_id=note_id,
            dialogue_session_id=state["dialogue_session_id"],
            understanding_level=feedback_data.understanding_level,
            **feedback_insert_fields(feedback_data, aspect_map),
        )

        if await review_schedule_repository.find_by_note_id(conn=conn, note_id=note_id) is None:
            await review_schedule_repository.insert(
                conn=conn, note_id=note_id, next_review_at=calculate_next_review(0)
            )

    return {}
