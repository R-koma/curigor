from typing import Any
from uuid import UUID

from core.database import DBConnection


async def find_by_user_id(conn: DBConnection, user_id: str) -> list[dict[str, Any]]:
    query = """--sql
    SELECT n.id, n.user_id, n.topic, n.content, n.summary, n.status,
           n.category, n.aspect_map, n.collection_id, n.suggested_collection,
           n.manually_edited_at, n.created_at, n.updated_at,
    COALESCE(rs.review_count, 0) AS review_count
    From notes n
    LEFT JOIN review_schedules rs ON rs.note_id = n.id
    WHERE n.user_id = $1 AND n.status IN ('active', 'archived')
    ORDER BY created_at DESC
  """

    records = await conn.fetch(query, user_id)
    return [dict(r) for r in records]


async def find_by_id(conn: DBConnection, note_id: UUID, user_id: str) -> dict[str, Any] | None:
    query = """--sql
    SELECT id, user_id, topic, content, summary, status, category, aspect_map, intake,
           collection_id, suggested_collection, manually_edited_at, created_at, updated_at
    FROM notes
    WHERE id = $1 AND user_id = $2
  """

    record = await conn.fetchrow(query, note_id, user_id)
    return dict(record) if record else None


async def find_categories_by_user_id(conn: DBConnection, user_id: str) -> list[str]:
    """ユーザーが既に使用しているカテゴリー名の一覧（重複なし）。カテゴリー推定時の寄せ先候補に使う。"""
    query = """--sql
    SELECT DISTINCT category
    FROM notes
    WHERE user_id = $1 AND category IS NOT NULL
    ORDER BY category
  """

    records = await conn.fetch(query, user_id)
    return [r["category"] for r in records]


async def insert(
    conn: DBConnection,
    note_id: UUID,
    user_id: str,
    topic: str,
    content: str,
    summary: str,
    category: str | None = None,
    aspect_map: str | None = None,
    suggested_collection: str | None = None,
    intake: str | None = None,
) -> dict[str, Any]:
    query = """--sql
        INSERT INTO notes (id, user_id, topic, content, summary, status, category, aspect_map,
                           suggested_collection, intake)
        VALUES ($1, $2, $3, $4, $5, 'active', $6, $7::jsonb, $8, $9::jsonb)
        RETURNING id, user_id, topic, content, summary, status, category, aspect_map, intake,
                  collection_id, suggested_collection, manually_edited_at, created_at, updated_at
    """
    record = await conn.fetchrow(
        query, note_id, user_id, topic, content, summary, category, aspect_map, suggested_collection, intake
    )
    assert record is not None
    return dict(record)


async def update_aspect_map(
    conn: DBConnection,
    note_id: UUID,
    aspect_map: str,
) -> None:
    query = """--sql
        UPDATE notes
        SET aspect_map = $2::jsonb, updated_at = NOW()
        WHERE id = $1
    """
    await conn.execute(query, note_id, aspect_map)


async def update(
    conn: DBConnection,
    note_id: UUID,
    user_id: str,
    topic: str | None = None,
    content: str | None = None,
    summary: str | None = None,
    status: str | None = None,
    category: str | None = None,
    mark_manually_edited: bool = False,
) -> dict[str, Any] | None:
    # mark_manually_edited はユーザーの手動編集パスでのみ True。復習再生成（update_note_and_feedback）は
    # 既定の False で呼ぶため、来歴フラグを誤って立てない（保護対象の判定は #235）
    query = """--sql
    UPDATE notes
    SET topic = COALESCE($3, topic),
        content = COALESCE($4, content),
        summary = COALESCE($5, summary),
        status = COALESCE($6, status),
        category = COALESCE($7, category),
        manually_edited_at = CASE WHEN $8 THEN NOW() ELSE manually_edited_at END,
        updated_at = NOW()
    WHERE id = $1 AND user_id = $2
    RETURNING id, user_id, topic, content, summary, status, category, aspect_map, intake,
              collection_id, suggested_collection, manually_edited_at, created_at, updated_at
  """

    record = await conn.fetchrow(
        query, note_id, user_id, topic, content, summary, status, category, mark_manually_edited
    )
    return dict(record) if record else None


async def delete(conn: DBConnection, note_id: UUID, user_id: str) -> bool:
    async with conn.transaction():
        await conn.execute(
            "DELETE FROM feedbacks WHERE note_id = $1",
            note_id,
        )
        await conn.execute(
            "DELETE FROM review_schedules WHERE note_id = $1",
            note_id,
        )
        result = await conn.execute(
            "DELETE FROM notes WHERE id = $1 AND user_id = $2",
            note_id,
            user_id,
        )
    deleted_count = int(result.split(" ")[1])
    return deleted_count > 0


async def set_collection(conn: DBConnection, note_id: UUID, user_id: str, collection_id: UUID | None) -> bool:
    result = await conn.execute(
        "UPDATE notes SET collection_id = $3, suggested_collection = NULL WHERE id = $1 AND user_id = $2",
        note_id,
        user_id,
        collection_id,
    )
    return int(result.split(" ")[1]) > 0


async def clear_suggested_collection(conn: DBConnection, note_id: UUID, user_id: str) -> bool:
    result = await conn.execute(
        "UPDATE notes SET suggested_collection = NULL WHERE id = $1 AND user_id = $2",
        note_id,
        user_id,
    )
    return int(result.split(" ")[1]) > 0


async def find_by_collection_id(conn: DBConnection, collection_id: UUID, user_id: str) -> list[dict[str, Any]]:
    query = """--sql
    SELECT n.id, n.topic, n.summary, n.status, n.created_at, COALESCE(rs.review_count, 0) AS review_count
    FROM notes n
    LEFT JOIN review_schedules rs ON rs.note_id = n.id
    WHERE n.collection_id = $1 AND n.user_id = $2
    ORDER BY n.created_at ASC
    """
    records = await conn.fetch(query, collection_id, user_id)
    return [dict(r) for r in records]


async def find_contents_by_collection_id(
    conn: DBConnection, collection_id: UUID, user_id: str
) -> list[dict[str, Any]]:
    query = """--sql
    SELECT n.id, n.topic, n.content,
           ARRAY(
               SELECT r.content FROM note_revisions r WHERE r.note_id = n.id ORDER BY r.created_at, r.id
           ) AS revisions
    FROM notes n
    WHERE n.collection_id = $1 AND n.user_id = $2
    ORDER BY n.created_at ASC
    """
    records = await conn.fetch(query, collection_id, user_id)
    return [{**dict(r), "revisions": list(r["revisions"])} for r in records]
