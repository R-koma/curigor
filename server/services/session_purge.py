from typing import Any
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver

from storage import ObjectStorage, dialogue_image_prefix


async def purge_sessions(
    checkpointer: BaseCheckpointSaver[Any], storage: ObjectStorage, session_ids: list[UUID]
) -> None:
    for session_id in session_ids:
        await checkpointer.adelete_thread(str(session_id))
        await storage.delete_prefix(dialogue_image_prefix(session_id))
