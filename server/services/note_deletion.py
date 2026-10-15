from typing import Any
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver

from core.database import DBConnection
from repositories import dialogue_session_repository, note_collection_repository, note_repository
from services.session_purge import purge_sessions
from storage import ObjectStorage


async def delete_note(
    conn: DBConnection,
    checkpointer: BaseCheckpointSaver[Any],
    storage: ObjectStorage,
    note_id: UUID,
    user_id: str,
) -> bool:
    session_ids = await dialogue_session_repository.find_ids_by_note(conn, note_id, user_id)
    await purge_sessions(checkpointer, storage, session_ids)
    async with conn.transaction():
        if not await note_repository.delete(conn, note_id, user_id):
            return False
        await dialogue_session_repository.delete_by_ids(conn, session_ids, user_id)
    return True


async def delete_collection(
    conn: DBConnection,
    checkpointer: BaseCheckpointSaver[Any],
    storage: ObjectStorage,
    collection_id: UUID,
    user_id: str,
) -> bool:
    session_ids = await dialogue_session_repository.find_ids_by_collection(conn, collection_id, user_id)
    await purge_sessions(checkpointer, storage, session_ids)
    async with conn.transaction():
        if not await note_collection_repository.delete(conn, collection_id, user_id):
            return False
        await dialogue_session_repository.delete_by_ids(conn, session_ids, user_id)
    return True
