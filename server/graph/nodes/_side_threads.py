import logging
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from core.database import get_pool
from graph.explore import side_threads_in_order
from graph.state import LearningState
from repositories import side_question_repository

logger = logging.getLogger(__name__)


async def load_side_threads(state: LearningState) -> list[Mapping[str, Any]]:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            threads = await side_question_repository.find_threads(conn, UUID(str(state["dialogue_session_id"])))
    except Exception:
        logger.exception("Failed to read side questions for session %s", state.get("dialogue_session_id"))
        return []
    return side_threads_in_order(threads)
