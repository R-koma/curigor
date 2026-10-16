import asyncio
import logging
from datetime import timedelta

import asyncpg

from repositories import dialogue_session_repository

logger = logging.getLogger(__name__)

STALE_GENERATION_AFTER = timedelta(minutes=3)
SWEEP_INTERVAL_SECONDS = 30.0


async def reset_stuck_generations(pool: asyncpg.Pool, stale_after: timedelta = STALE_GENERATION_AFTER) -> int:
    async with pool.acquire() as conn:
        session_ids = await dialogue_session_repository.reset_stuck_generations(conn, stale_after)
    if session_ids:
        logger.warning(
            "reset %d stuck generation(s) older than %s: %s",
            len(session_ids),
            stale_after,
            ", ".join(str(session_id) for session_id in session_ids),
        )
    return len(session_ids)


async def reset_stuck_generations_periodically(
    pool: asyncpg.Pool,
    interval_seconds: float = SWEEP_INTERVAL_SECONDS,
    stale_after: timedelta = STALE_GENERATION_AFTER,
) -> None:
    while True:
        try:
            await reset_stuck_generations(pool, stale_after)
        except Exception:
            logger.warning("failed to reset stuck generations", exc_info=True)
        await asyncio.sleep(interval_seconds)
