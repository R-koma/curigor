import logging
from uuid import UUID

from core import config
from core.database import DBConnection
from repositories import note_embedding_repository, note_repository
from schemas.note_collection import MAX_COLLECTION_NAME_LENGTH

logger = logging.getLogger(__name__)


async def suggest_collection_by_similarity(conn: DBConnection, note_id: UUID, user_id: str) -> str | None:
    """近いノートが入っているまとめノートを、束ね先の候補として note に入れる。入れた名前を返す。

    LLM が決めた候補（生成時）がある、断られた、すでに束ねてある、のいずれかなら何もしない。
    """
    votes = await note_embedding_repository.find_collection_votes(
        conn,
        note_id,
        user_id,
        limit=config.COLLECTION_SUGGESTION_NEIGHBORS,
        min_similarity=config.COLLECTION_SUGGESTION_MIN_SIMILARITY,
    )
    if not votes:
        return None
    name: str = votes[0]["name"][:MAX_COLLECTION_NAME_LENGTH]
    if not await note_repository.set_suggested_collection_if_unsuggested(conn, note_id, user_id, name):
        return None
    logger.info("suggested collection %r for note %s (score=%.3f)", name, note_id, votes[0]["score"])
    return name
