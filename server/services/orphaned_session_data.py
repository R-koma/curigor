import logging
from typing import Any
from uuid import UUID

import asyncpg
from langgraph.checkpoint.base import BaseCheckpointSaver

from repositories import dialogue_session_repository
from storage import DIALOGUE_IMAGES_PREFIX, ObjectStorage, dialogue_image_prefix

logger = logging.getLogger(__name__)


def _parse_uuid(value: str) -> UUID | None:
    try:
        parsed = UUID(value)
    except ValueError:
        return None
    return parsed if str(parsed) == value else None


async def purge_orphaned_session_data(
    pool: asyncpg.Pool, checkpointer: BaseCheckpointSaver[Any], storage: ObjectStorage
) -> None:
    async with pool.acquire() as conn:
        thread_ids = await dialogue_session_repository.find_orphaned_checkpoint_thread_ids(conn)
    for thread_id in thread_ids:
        await checkpointer.adelete_thread(thread_id)

    image_session_ids = [
        session_id
        for name in await storage.list_child_prefixes(DIALOGUE_IMAGES_PREFIX)
        if (session_id := _parse_uuid(name)) is not None
    ]
    async with pool.acquire() as conn:
        existing = await dialogue_session_repository.find_existing_ids(conn, image_session_ids)
    orphaned_images = [session_id for session_id in image_session_ids if session_id not in existing]
    for session_id in orphaned_images:
        await storage.delete_prefix(dialogue_image_prefix(session_id))

    if thread_ids or orphaned_images:
        logger.info(
            "purged orphaned session data: %d checkpoint threads, %d image prefixes",
            len(thread_ids),
            len(orphaned_images),
        )


async def purge_orphaned_session_data_in_background(
    pool: asyncpg.Pool, checkpointer: BaseCheckpointSaver[Any], storage: ObjectStorage
) -> None:
    try:
        await purge_orphaned_session_data(pool, checkpointer, storage)
    except Exception:
        logger.warning("failed to purge orphaned session data", exc_info=True)
