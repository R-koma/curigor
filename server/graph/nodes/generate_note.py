import asyncio
import json
import logging
import uuid
from typing import Any
from uuid import UUID

from langchain_core.messages import SystemMessage

from core.database import DBConnection, get_pool
from graph.intake_summary import build_intake_summary
from graph.llm import llm_structured
from graph.output_schemas import AspectMap, CollectionSuggestion, NoteCategory, NoteContent
from graph.prompts import GENERATE_ASPECT_MAP_PROMPT, GENERATE_CATEGORY_PROMPT, GENERATE_NOTE_PROMPT
from graph.prompts.collection import build_collection_suggestion_prompt
from graph.state import LearningState
from repositories import note_collection_repository, note_repository
from schemas.note_collection import MAX_COLLECTION_NAME_LENGTH

logger = logging.getLogger(__name__)


async def _estimate_category(
    conn: DBConnection,
    user_id: str,
    conversation_text: str,
) -> str | None:
    """対話内容からカテゴリーを推定する。既存カテゴリーへ寄せて乱立を防ぐ。

    一覧での即時グルーピング表示のため inline で実行するが、失敗してもノート生成は止めない。
    """
    existing = await note_repository.find_categories_by_user_id(conn, user_id)
    existing_block = "\n".join(f"- {c}" for c in existing) if existing else "（まだカテゴリーはありません）"
    prompt = GENERATE_CATEGORY_PROMPT.format(existing_categories=existing_block)

    category_llm = llm_structured.with_structured_output(NoteCategory)
    try:
        result: Any = await category_llm.ainvoke(
            [
                SystemMessage(content=prompt),
                {"role": "user", "content": conversation_text},
            ],
            config={"run_name": "estimate-category"},
        )
    except Exception:
        logger.warning("category estimation failed for user %s", user_id, exc_info=True)
        return None

    if not isinstance(result, NoteCategory):
        logger.warning("category estimation returned unexpected type for user %s", user_id)
        return None

    category = result.category.strip()
    return category or None


async def _suggest_collection(conn: DBConnection, user_id: str, *, topic: str, source: str) -> str | None:
    existing = await note_collection_repository.find_names_by_user_id(conn, user_id)
    if not source.strip() and not existing:
        return None
    prompt = build_collection_suggestion_prompt(topic=topic, source=source, existing_collections=existing)
    try:
        result: Any = await llm_structured.with_structured_output(CollectionSuggestion).ainvoke(
            [SystemMessage(content=prompt)], config={"run_name": "suggest-collection"}
        )
    except Exception:
        logger.warning("collection suggestion failed for user %s", user_id, exc_info=True)
        return None
    if not isinstance(result, CollectionSuggestion):
        return None
    return result.name.strip()[:MAX_COLLECTION_NAME_LENGTH] or None


async def _generate_aspect_map_background(
    note_id: UUID,
    conversation_text: str,
) -> None:
    aspect_llm = llm_structured.with_structured_output(AspectMap)
    try:
        aspect_result: Any = await aspect_llm.ainvoke(
            [
                SystemMessage(content=GENERATE_ASPECT_MAP_PROMPT),
                {"role": "user", "content": conversation_text},
            ],
            config={"run_name": "generate-aspect-map"},
        )
    except Exception:
        logger.warning("aspect map generation failed for note %s", note_id, exc_info=True)
        return

    if not isinstance(aspect_result, AspectMap):
        logger.warning("aspect map generation returned unexpected type for note %s", note_id)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        await note_repository.update_aspect_map(conn, note_id, aspect_result.model_dump_json())


async def generate_note(state: LearningState) -> dict[str, Any]:
    """会話内容からノートを生成し DB に保存。観点マップは後追いで生成する"""

    conversation_text = ""
    for msg in state["messages"]:
        role = "ユーザー" if msg.type == "human" else "アシスタント"
        conversation_text += f"{role}: {msg.content}\n"

    note_llm = llm_structured.with_structured_output(NoteContent)
    note_result: Any = await note_llm.ainvoke(
        [
            SystemMessage(content=GENERATE_NOTE_PROMPT),
            {"role": "user", "content": conversation_text},
        ],
        config={"run_name": "generate-note-content"},
    )
    if not isinstance(note_result, NoteContent):
        raise RuntimeError("LLM did not return structured NoteContent output")

    note_id = uuid.uuid4()
    pool = await get_pool()

    intake_summary = build_intake_summary(state)
    intake = json.dumps(intake_summary.model_dump(), ensure_ascii=False) if intake_summary else None

    async with pool.acquire() as conn:
        category = await _estimate_category(conn, state["user_id"], conversation_text)
        suggested_collection = await _suggest_collection(
            conn, state["user_id"], topic=note_result.topic, source=state.get("learning_source") or ""
        )
        await note_repository.insert(
            conn=conn,
            note_id=note_id,
            user_id=state["user_id"],
            topic=note_result.topic,
            content=note_result.content,
            summary=note_result.summary,
            category=category,
            aspect_map=None,
            suggested_collection=suggested_collection,
            intake=intake,
        )

    asyncio.create_task(_generate_aspect_map_background(note_id, conversation_text))

    return {
        "note_id": note_id,
    }


__all__ = ["generate_note"]
