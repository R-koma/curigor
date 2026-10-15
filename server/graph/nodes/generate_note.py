import asyncio
import json
import logging
import uuid
from typing import Any
from uuid import UUID

from langchain_core.messages import SystemMessage

from core.database import get_pool
from graph.intake_summary import build_intake_summary
from graph.llm import llm_structured
from graph.nodes._aspect_map_generation import conversation_text_for_aspect_map, generate_aspect_map
from graph.nodes._feedback_assessment import analyze_dialogue, format_conversation_history
from graph.output_schemas import CollectionSuggestion, DialogueAnalysis, NoteCategory, NoteContent
from graph.prompts import GENERATE_CATEGORY_PROMPT, GENERATE_NOTE_PROMPT
from graph.prompts.collection import build_collection_suggestion_prompt
from graph.prompts.note import NOTE_PROMPT_FINGERPRINT
from graph.state import FeedbackInputs, LearningState
from repositories import note_collection_repository, note_repository
from schemas.note_collection import MAX_COLLECTION_NAME_LENGTH
from services.note_embedding import schedule_note_embedding

logger = logging.getLogger(__name__)

_METADATA = {"prompt_fingerprint": NOTE_PROMPT_FINGERPRINT}


async def _estimate_category(existing: list[str], user_id: str, conversation_text: str) -> str | None:
    """対話内容からカテゴリーを推定する。既存カテゴリーへ寄せて乱立を防ぐ。

    一覧での即時グルーピング表示のため inline で実行するが、失敗してもノート生成は止めない。
    """
    existing_block = "\n".join(f"- {c}" for c in existing) if existing else "（まだカテゴリーはありません）"
    prompt = GENERATE_CATEGORY_PROMPT.format(existing_categories=existing_block)

    category_llm = llm_structured.with_structured_output(NoteCategory, task="estimate-category")
    try:
        result: Any = await category_llm.ainvoke(
            [
                SystemMessage(content=prompt),
                {"role": "user", "content": conversation_text},
            ],
            config={"run_name": "estimate-category", "metadata": _METADATA},
        )
    except Exception:
        logger.warning("category estimation failed for user %s", user_id, exc_info=True)
        return None

    if not isinstance(result, NoteCategory):
        logger.warning("category estimation returned unexpected type for user %s", user_id)
        return None

    category = result.category.strip()
    return category or None


async def _suggest_collection(existing: list[str], user_id: str, *, topic: str, source: str) -> str | None:
    if not source.strip() and not existing:
        return None
    prompt = build_collection_suggestion_prompt(topic=topic, source=source, existing_collections=existing)
    try:
        result: Any = await llm_structured.with_structured_output(
            CollectionSuggestion, task="suggest-collection"
        ).ainvoke([SystemMessage(content=prompt)], config={"run_name": "suggest-collection", "metadata": _METADATA})
    except Exception:
        logger.warning("collection suggestion failed for user %s", user_id, exc_info=True)
        return None
    if not isinstance(result, CollectionSuggestion):
        return None
    return result.name.strip()[:MAX_COLLECTION_NAME_LENGTH] or None


async def _note_content(conversation_text: str) -> NoteContent:
    note_llm = llm_structured.with_structured_output(NoteContent, task="generate-note-content")
    note_result: Any = await note_llm.ainvoke(
        [
            SystemMessage(content=GENERATE_NOTE_PROMPT),
            {"role": "user", "content": conversation_text},
        ],
        config={"run_name": "generate-note-content", "metadata": _METADATA},
    )
    if not isinstance(note_result, NoteContent):
        raise RuntimeError("LLM did not return structured NoteContent output")
    return note_result


async def _note_and_collection(
    conversation_text: str, existing_collections: list[str], user_id: str, source: str
) -> tuple[NoteContent, str | None]:
    note_result = await _note_content(conversation_text)
    suggested = await _suggest_collection(existing_collections, user_id, topic=note_result.topic, source=source)
    return note_result, suggested


async def _analysis_or_none(state: LearningState, note_id: UUID) -> DialogueAnalysis | None:
    try:
        return await analyze_dialogue(state["topic"], format_conversation_history(state["messages"]))
    except Exception:
        logger.warning("dialogue analysis failed for note %s; generate_feedback will retry", note_id, exc_info=True)
        return None


async def generate_note(state: LearningState) -> dict[str, Any]:
    """会話内容からノートを生成し DB に保存する。フィードバックの分析と観点マップも並行に作る"""

    user_id = state["user_id"]
    conversation_text = conversation_text_for_aspect_map(state["messages"])
    note_id = uuid.uuid4()
    pool = await get_pool()

    async with pool.acquire() as conn:
        existing_categories = await note_repository.find_categories_by_user_id(conn, user_id)
        existing_collections = await note_collection_repository.find_names_by_user_id(conn, user_id)

    (note_result, suggested_collection), category, analysis, aspect_map_model = await asyncio.gather(
        _note_and_collection(conversation_text, existing_collections, user_id, state.get("learning_source") or ""),
        _estimate_category(existing_categories, user_id, conversation_text),
        _analysis_or_none(state, note_id),
        generate_aspect_map(conversation_text, note_id),
    )

    intake_summary = build_intake_summary(state)
    intake = json.dumps(intake_summary.model_dump(), ensure_ascii=False) if intake_summary else None

    async with pool.acquire() as conn:
        await note_repository.insert(
            conn=conn,
            note_id=note_id,
            user_id=user_id,
            topic=note_result.topic,
            content=note_result.content,
            summary=note_result.summary,
            category=category,
            aspect_map=aspect_map_model.model_dump_json() if aspect_map_model is not None else None,
            suggested_collection=suggested_collection,
            intake=intake,
            prompt_fingerprint=NOTE_PROMPT_FINGERPRINT,
        )

    schedule_note_embedding(note_id, user_id)

    feedback_inputs: FeedbackInputs | None = None
    if analysis is not None:
        feedback_inputs = {
            "analysis": analysis.model_dump(),
            "aspect_map": aspect_map_model.model_dump() if aspect_map_model is not None else None,
        }
    return {"note_id": note_id, "feedback_inputs": feedback_inputs}


__all__ = ["generate_note"]
