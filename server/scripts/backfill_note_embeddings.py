"""埋め込みの無いノートに埋め込みを作り、束ね先とつながりの候補を入れる。

`uv run python -m scripts.backfill_note_embeddings`
"""

import asyncio
import logging

from core.database import close_pool, get_pool
from embedding import get_embedder
from repositories import note_embedding_repository
from services.collection_suggestion import suggest_collection_by_similarity
from services.note_embedding import refresh_note_embedding
from services.note_links import suggest_note_links


async def main() -> None:
    embedder = get_embedder()
    pool = await get_pool()
    async with pool.acquire() as conn:
        targets = await note_embedding_repository.find_note_ids_without_embedding(conn, embedder.model)
    created = 0
    for note_id, user_id in targets:
        if await refresh_note_embedding(note_id, user_id, embedder):
            created += 1
    async with pool.acquire() as conn:
        unsuggested = await note_embedding_repository.find_unsuggested_note_ids(conn, embedder.model)
        suggested = 0
        for note_id, user_id in unsuggested:
            if await suggest_collection_by_similarity(conn, note_id, user_id):
                suggested += 1
        embedded = await note_embedding_repository.find_embedded_note_ids(conn, embedder.model)
        linked = 0
        for note_id, user_id in embedded:
            if await suggest_note_links(conn, note_id, user_id):
                linked += 1
    await close_pool()
    print(
        f"embedded {created}/{len(targets)} notes, suggested a collection for {suggested}/{len(unsuggested)} notes, "
        f"suggested links for {linked}/{len(embedded)} notes"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
