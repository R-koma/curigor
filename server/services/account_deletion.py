from typing import Any

import asyncpg
from langgraph.checkpoint.base import BaseCheckpointSaver

from observability.langfuse_tracing import delete_user_traces
from repositories import dialogue_message_image_repository, dialogue_session_repository
from storage import ObjectStorage


async def purge_user_data(
    pool: asyncpg.Pool, checkpointer: BaseCheckpointSaver[Any], storage: ObjectStorage, user_id: str
) -> None:
    async with pool.acquire() as conn:
        session_ids = await dialogue_session_repository.find_ids_by_user(conn, user_id)
        storage_keys = await dialogue_message_image_repository.find_storage_keys_by_user(conn, user_id)
    for session_id in session_ids:
        await checkpointer.adelete_thread(str(session_id))
    for key in storage_keys:
        await storage.delete(key)
    await delete_user_traces(user_id)
