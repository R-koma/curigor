from typing import Any

import asyncpg
from langgraph.checkpoint.base import BaseCheckpointSaver

from observability.langfuse_tracing import delete_user_traces
from repositories import dialogue_session_repository
from storage import ObjectStorage, dialogue_image_prefix


async def purge_user_data(
    pool: asyncpg.Pool, checkpointer: BaseCheckpointSaver[Any], storage: ObjectStorage, user_id: str
) -> None:
    async with pool.acquire() as conn:
        session_ids = await dialogue_session_repository.find_ids_by_user(conn, user_id)
    for session_id in session_ids:
        await checkpointer.adelete_thread(str(session_id))
        await storage.delete_prefix(dialogue_image_prefix(session_id))
    await delete_user_traces(user_id)
