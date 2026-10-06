from collections.abc import Sequence
from typing import Any
from uuid import UUID

from core.database import DBConnection


def _to_vector_literal(embedding: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in embedding) + "]"


async def find_content_hash(conn: DBConnection, note_id: UUID, model: str) -> str | None:
    query = """--sql
    SELECT content_hash FROM note_embeddings WHERE note_id = $1 AND model = $2
    """
    value: str | None = await conn.fetchval(query, note_id, model)
    return value


async def upsert(
    conn: DBConnection,
    note_id: UUID,
    user_id: str,
    embedding: Sequence[float],
    model: str,
    content_hash: str,
) -> None:
    query = """--sql
    INSERT INTO note_embeddings (note_id, user_id, embedding, model, content_hash)
    SELECT n.id, n.user_id, $3::vector, $4, $5
    FROM notes n
    WHERE n.id = $1 AND n.user_id = $2
    ON CONFLICT (note_id) DO UPDATE
    SET embedding = EXCLUDED.embedding,
        model = EXCLUDED.model,
        content_hash = EXCLUDED.content_hash,
        updated_at = NOW()
    """
    await conn.execute(query, note_id, user_id, _to_vector_literal(embedding), model, content_hash)


async def find_similar_notes(
    conn: DBConnection,
    note_id: UUID,
    user_id: str,
    limit: int,
    min_similarity: float,
) -> list[dict[str, Any]]:
    """note_id の埋め込みに近い、同じユーザーの他のノート（類似度の降順）。"""
    query = """--sql
    SELECT note_id, similarity FROM (
        SELECT e.note_id, 1 - (e.embedding <=> src.embedding) AS similarity
        FROM note_embeddings src
        JOIN note_embeddings e ON e.user_id = src.user_id AND e.model = src.model AND e.note_id <> src.note_id
        WHERE src.note_id = $1 AND src.user_id = $2
        ORDER BY e.embedding <=> src.embedding
        LIMIT $3
    ) nearest
    WHERE similarity >= $4
    ORDER BY similarity DESC
    """
    records = await conn.fetch(query, note_id, user_id, limit, min_similarity)
    return [dict(r) for r in records]


async def find_collection_votes(
    conn: DBConnection,
    note_id: UUID,
    user_id: str,
    limit: int,
    min_similarity: float,
) -> list[dict[str, Any]]:
    """note_id に近いノートのうち、まとめノートに入っているものを、まとめノートごとに集計する。

    score は近いノートの類似度の合計、best は最も近いノートの類似度。score の降順。
    """
    query = """--sql
    SELECT c.id AS collection_id, c.name, SUM(nearest.similarity) AS score, MAX(nearest.similarity) AS best
    FROM (
        SELECT e.note_id, 1 - (e.embedding <=> src.embedding) AS similarity
        FROM note_embeddings src
        JOIN note_embeddings e ON e.user_id = src.user_id AND e.model = src.model AND e.note_id <> src.note_id
        WHERE src.note_id = $1 AND src.user_id = $2
        ORDER BY e.embedding <=> src.embedding
        LIMIT $3
    ) nearest
    JOIN notes n ON n.id = nearest.note_id
    JOIN note_collections c ON c.id = n.collection_id
    WHERE nearest.similarity >= $4
    GROUP BY c.id, c.name
    ORDER BY score DESC, best DESC
    """
    records = await conn.fetch(query, note_id, user_id, limit, min_similarity)
    return [dict(r) for r in records]


async def find_unsuggested_note_ids(conn: DBConnection, model: str) -> list[tuple[UUID, str]]:
    """埋め込みがあり、まとめノートにも候補にも入っておらず、候補を断られてもいないノート。"""
    query = """--sql
    SELECT n.id, n.user_id
    FROM notes n
    JOIN note_embeddings e ON e.note_id = n.id AND e.model = $1
    WHERE n.collection_id IS NULL
      AND n.suggested_collection IS NULL
      AND n.collection_suggestion_dismissed_at IS NULL
    ORDER BY n.created_at
    """
    records = await conn.fetch(query, model)
    return [(r["id"], r["user_id"]) for r in records]


async def find_note_ids_without_embedding(conn: DBConnection, model: str) -> list[tuple[UUID, str]]:
    query = """--sql
    SELECT n.id, n.user_id
    FROM notes n
    LEFT JOIN note_embeddings e ON e.note_id = n.id AND e.model = $1
    WHERE e.note_id IS NULL
    ORDER BY n.created_at
    """
    records = await conn.fetch(query, model)
    return [(r["id"], r["user_id"]) for r in records]
