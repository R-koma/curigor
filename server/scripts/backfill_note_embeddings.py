"""埋め込みの無いノートに埋め込みを作る。`uv run python -m scripts.backfill_note_embeddings`"""

import asyncio
import logging

from core.database import close_pool, get_pool
from embedding import get_embedder
from repositories import note_embedding_repository
from services.note_embedding import refresh_note_embedding


async def main() -> None:
    embedder = get_embedder()
    pool = await get_pool()
    async with pool.acquire() as conn:
        targets = await note_embedding_repository.find_note_ids_without_embedding(conn, embedder.model)
    created = 0
    for note_id, user_id in targets:
        if await refresh_note_embedding(note_id, user_id, embedder):
            created += 1
    await close_pool()
    print(f"embedded {created}/{len(targets)} notes")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
