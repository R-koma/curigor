from typing import Any, Literal
from uuid import UUID

from core.database import DBConnection

NoteLinkStatus = Literal["suggested", "accepted", "dismissed"]


async def find_link_candidates(
    conn: DBConnection,
    note_id: UUID,
    user_id: str,
    limit: int,
    min_similarity: float,
) -> list[dict[str, Any]]:
    """note_id に近い、同じユーザーの別のまとめノート（または未所属）のノート（類似度の降順）。"""
    query = """--sql
    SELECT note_id, similarity FROM (
        SELECT e.note_id, 1 - (e.embedding <=> src.embedding) AS similarity
        FROM note_embeddings src
        JOIN notes self ON self.id = src.note_id
        JOIN note_embeddings e ON e.user_id = src.user_id AND e.model = src.model AND e.note_id <> src.note_id
        JOIN notes other ON other.id = e.note_id
        WHERE src.note_id = $1 AND src.user_id = $2
          AND (self.collection_id IS NULL OR other.collection_id IS DISTINCT FROM self.collection_id)
        ORDER BY e.embedding <=> src.embedding
        LIMIT $3
    ) nearest
    WHERE similarity >= $4
    ORDER BY similarity DESC
    """
    records = await conn.fetch(query, note_id, user_id, limit, min_similarity)
    return [dict(r) for r in records]


async def upsert_suggestions(
    conn: DBConnection, note_id: UUID, user_id: str, candidates: list[dict[str, Any]]
) -> None:
    """候補をつながりとして残す。既にあるつながりは類似度だけを更新し、採否は変えない。"""
    query = """--sql
    INSERT INTO note_links (user_id, note_id_a, note_id_b, similarity)
    VALUES ($1, LEAST($2::uuid, $3::uuid), GREATEST($2::uuid, $3::uuid), $4)
    ON CONFLICT (note_id_a, note_id_b) DO UPDATE
    SET similarity = EXCLUDED.similarity,
        updated_at = NOW()
    """
    await conn.executemany(query, [(user_id, note_id, c["note_id"], c["similarity"]) for c in candidates])


async def delete_weak_suggestions(conn: DBConnection, note_id: UUID, user_id: str, min_similarity: float) -> None:
    """note_id の未回答の候補のうち、埋め込みを作り直した後の類似度が下限を下回ったものを消す。"""
    query = """--sql
    DELETE FROM note_links l
    USING note_embeddings ea, note_embeddings eb
    WHERE l.user_id = $2
      AND l.status = 'suggested'
      AND (l.note_id_a = $1 OR l.note_id_b = $1)
      AND ea.note_id = l.note_id_a
      AND eb.note_id = l.note_id_b
      AND ea.model = eb.model
      AND 1 - (ea.embedding <=> eb.embedding) < $3
    """
    await conn.execute(query, note_id, user_id, min_similarity)


async def find_by_note_id(conn: DBConnection, note_id: UUID, user_id: str) -> list[dict[str, Any]]:
    """note_id のつながり（採用済みと未回答の候補）を、相手のノートとともに返す。

    同じまとめノートに入った相手の候補は返さない（候補を作った後に束ねた場合）。
    """
    query = """--sql
    SELECT l.id, l.status, l.similarity,
           other.id AS note_id, other.topic, other.summary, other.collection_id, c.name AS collection_name
    FROM note_links l
    JOIN notes self ON self.id = $1 AND self.user_id = $2
    JOIN notes other ON other.id = CASE WHEN l.note_id_a = $1 THEN l.note_id_b ELSE l.note_id_a END
    LEFT JOIN note_collections c ON c.id = other.collection_id
    WHERE l.user_id = $2
      AND (l.note_id_a = $1 OR l.note_id_b = $1)
      AND (
          l.status = 'accepted'
          OR (
              l.status = 'suggested'
              AND (self.collection_id IS NULL OR other.collection_id IS DISTINCT FROM self.collection_id)
          )
      )
    ORDER BY (l.status = 'accepted') DESC, l.similarity DESC
    """
    records = await conn.fetch(query, note_id, user_id)
    return [dict(r) for r in records]


async def set_status(conn: DBConnection, link_id: UUID, note_id: UUID, user_id: str, status: NoteLinkStatus) -> bool:
    query = """--sql
    UPDATE note_links
    SET status = $4, updated_at = NOW()
    WHERE id = $1 AND user_id = $3 AND (note_id_a = $2 OR note_id_b = $2)
    RETURNING id
    """
    return await conn.fetchval(query, link_id, note_id, user_id, status) is not None
