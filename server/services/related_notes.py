import asyncio
import logging

from core import config
from core.database import get_pool
from embedding import Embedder, get_embedder
from graph.state import RelatedNote
from observability.langfuse_tracing import traced_related_notes_query
from repositories import note_embedding_repository

logger = logging.getLogger(__name__)


def build_query_text(*, topic: str, purpose: str) -> str:
    return "\n\n".join(part for part in (topic.strip(), purpose.strip()) if part)


async def _search(user_id: str, text: str, embedder: Embedder) -> list[RelatedNote]:
    async with traced_related_notes_query(model=embedder.model, characters=len(text)):
        vector = await embedder.embed(text)
    pool = await get_pool()
    async with pool.acquire() as conn:
        records = await note_embedding_repository.find_notes_near_embedding(
            conn,
            user_id,
            vector,
            embedder.model,
            limit=config.RELATED_NOTES_LIMIT,
            min_similarity=config.RELATED_NOTES_MIN_SIMILARITY,
        )
    logger.info("related notes: %s", [(r["topic"], round(r["similarity"], 3)) for r in records])
    return [
        RelatedNote(
            note_id=str(r["note_id"]),
            topic=r["topic"],
            summary=(r["summary"] or "")[: config.MAX_RELATED_NOTE_SUMMARY_CHARS],
        )
        for r in records
    ]


async def find_related_notes(
    *, user_id: str, topic: str, purpose: str, embedder: Embedder | None = None
) -> list[RelatedNote]:
    """学習の開始時に引き合いに出す過去のノート。失敗したら空にする（学習は止めない）。"""
    text = build_query_text(topic=topic, purpose=purpose)
    if not text:
        return []
    try:
        return await asyncio.wait_for(
            _search(user_id, text, embedder or get_embedder()), timeout=config.RELATED_NOTES_TIMEOUT_SECONDS
        )
    except Exception:
        logger.warning("related notes lookup failed", exc_info=True)
        return []
