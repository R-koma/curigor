import logging
from uuid import UUID

from core import config
from core.database import DBConnection
from repositories import note_link_repository

logger = logging.getLogger(__name__)


async def suggest_note_links(conn: DBConnection, note_id: UUID, user_id: str) -> int:
    """近い別のまとめノート（または未所属）のノートを、つながりの候補として残す。残した候補の数を返す。

    断られた・採用済みのつながりは採否を変えない。作り直した後に下限を下回った未回答の候補は消す。
    """
    await note_link_repository.delete_weak_suggestions(conn, note_id, user_id, config.NOTE_LINK_MIN_SIMILARITY)
    candidates = await note_link_repository.find_link_candidates(
        conn, note_id, user_id, limit=config.NOTE_LINK_LIMIT, min_similarity=config.NOTE_LINK_MIN_SIMILARITY
    )
    if candidates:
        await note_link_repository.upsert_suggestions(conn, note_id, user_id, candidates)
    logger.info("note links for %s: %s", note_id, [(str(c["note_id"]), round(c["similarity"], 3)) for c in candidates])
    return len(candidates)
