import asyncio
from typing import Any

from langchain_core.messages import SystemMessage

from core.database import get_pool
from graph.aspect_map import feedback_insert_fields
from graph.llm import llm_structured
from graph.nodes._aspect_map_generation import conversation_text_for_aspect_map, generate_aspect_map
from graph.output_schemas import DialogueAnalysis, FeedbackOutput
from graph.prompts import ANALYZE_RESPONSE_PROMPT, GENERATE_FEEDBACK_PROMPT
from graph.prompts.feedback import build_aspect_section
from graph.state import LearningState
from repositories import feedback_repository, note_repository, review_schedule_repository
from services.review_scheduler import calculate_next_review


async def generate_feedback(state: LearningState) -> dict[str, Any]:
    """会話履歴を分析し、理解度評価を生成してDBに保存"""

    pool = await get_pool()
    topic = state["topic"]

    conversation_history = "\n".join(
        f"{'ユーザー' if msg.type == 'human' else 'AI'}: {msg.content}" for msg in state["messages"]
    )
    analyze_prompt = ANALYZE_RESPONSE_PROMPT.format(
        topic=topic,
        conversation_history=conversation_history,
    )
    analysis_llm = llm_structured.with_structured_output(DialogueAnalysis, task="analyze-dialogue")
    note_id = state["note_id"]
    analysis_data, aspect_map_model = await asyncio.gather(
        analysis_llm.ainvoke([SystemMessage(content=analyze_prompt)], config={"run_name": "analyze-dialogue"}),
        generate_aspect_map(conversation_text_for_aspect_map(state["messages"]), note_id),
    )
    if not isinstance(analysis_data, DialogueAnalysis):
        raise RuntimeError("LLM did not return structured DialogueAnalysis")
    analysis = analysis_data.to_markdown()

    aspect_map = aspect_map_model.model_dump() if aspect_map_model is not None else None

    feedback_prompt = GENERATE_FEEDBACK_PROMPT.format(
        topic=topic, analysis=analysis, aspect_section=build_aspect_section(aspect_map)
    )
    structured_llm = llm_structured.with_structured_output(FeedbackOutput, task="generate-feedback-scores")

    async with pool.acquire() as conn:
        if aspect_map_model is not None:
            await note_repository.update_aspect_map(conn, note_id, aspect_map_model.model_dump_json())
        note = await note_repository.find_by_id(conn, note_id, state["user_id"])
        if not note:
            raise RuntimeError(f"Note {note_id} not found")
        note_text = f"トピック: {note['topic']}\n\n{note['content']}"

        feedback_data = await structured_llm.ainvoke(
            [
                SystemMessage(content=feedback_prompt),
                {"role": "user", "content": note_text},
            ],
            config={"run_name": "generate-feedback-scores"},
        )

        if not isinstance(feedback_data, FeedbackOutput):
            raise RuntimeError("LLM did not return structured FeedbackOutput")

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
