import asyncio
import hashlib
import logging
from collections.abc import Sequence
from uuid import UUID

from core import config
from core.database import get_pool
from embedding import Embedder, EmbeddingError, get_embedder
from observability.langfuse_tracing import traced_embedding
from repositories import note_embedding_repository, note_repository, note_revision_repository

logger = logging.getLogger(__name__)

# asyncio はタスクを弱参照でしか持たないため、完了まで参照を保持する
_pending: set[asyncio.Task[None]] = set()


def build_embedding_text(*, topic: str, summary: str, content: str, revisions: Sequence[str]) -> str:
    text = "\n\n".join([topic, summary, content, *revisions])
    return text[: config.MAX_EMBEDDING_INPUT_CHARS]


def embedding_content_hash(text: str, model: str) -> str:
    return hashlib.sha256(f"{model}\x00{text}".encode()).hexdigest()


async def refresh_note_embedding(note_id: UUID, user_id: str, embedder: Embedder | None = None) -> bool:
    """ノートの埋め込みを作り直す。本文が前回と同じなら API を呼ばない。作り直したら True。"""
    embedder = embedder or get_embedder()
    pool = await get_pool()
    async with pool.acquire() as conn:
        note = await note_repository.find_by_id(conn, note_id, user_id)
        if note is None:
            return False
        revisions = await note_revision_repository.find_by_note_id(conn, note_id, user_id)
        text = build_embedding_text(
            topic=note["topic"],
            summary=note["summary"] or "",
            content=note["content"],
            revisions=[r["content"] for r in revisions],
        )
        content_hash = embedding_content_hash(text, embedder.model)
        if await note_embedding_repository.find_content_hash(conn, note_id, embedder.model) == content_hash:
            return False

    try:
        async with traced_embedding(user_id=user_id, note_id=note_id, model=embedder.model, characters=len(text)):
            vector = await embedder.embed(text)
    except EmbeddingError:
        logger.warning("embedding failed for note %s", note_id, exc_info=True)
        return False

    async with pool.acquire() as conn:
        await note_embedding_repository.upsert(conn, note_id, user_id, vector, embedder.model, content_hash)
    return True


async def _refresh_quietly(note_id: UUID, user_id: str) -> None:
    try:
        await refresh_note_embedding(note_id, user_id)
    except Exception:
        logger.warning("embedding refresh failed for note %s", note_id, exc_info=True)


def schedule_note_embedding(note_id: UUID, user_id: str) -> None:
    task = asyncio.create_task(_refresh_quietly(note_id, user_id))
    _pending.add(task)
    task.add_done_callback(_pending.discard)
