from typing import Any

import asyncpg
from langgraph.checkpoint.base import BaseCheckpointSaver

from observability.langfuse_tracing import delete_user_traces
from repositories import dialogue_session_repository
from services.session_purge import purge_sessions
from storage import ObjectStorage, avatar_prefix


async def purge_user_data(
    pool: asyncpg.Pool, checkpointer: BaseCheckpointSaver[Any], storage: ObjectStorage, user_id: str
) -> None:
    async with pool.acquire() as conn:
        session_ids = await dialogue_session_repository.find_ids_by_user(conn, user_id)
    await purge_sessions(checkpointer, storage, session_ids)
    await storage.delete_prefix(avatar_prefix(user_id))
    await delete_user_traces(user_id)
