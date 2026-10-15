from typing import Any
from uuid import UUID

from core.database import DBConnection


async def insert_many(
    conn: DBConnection,
    dialogue_message_id: UUID,
    images: list[tuple[str, str]],
) -> None:
    """1 メッセージに紐づく画像メタをまとめて保存する。

    images は (storage_key, mime_type) の並びで、添付順を image_order に反映する。
    """
    if not images:
        return
    query = """--sql
    INSERT INTO dialogue_message_images (dialogue_message_id, storage_key, mime_type, image_order)
    VALUES ($1, $2, $3, $4)
    """
    await conn.executemany(
        query,
        [(str(dialogue_message_id), key, mime, order) for order, (key, mime) in enumerate(images)],
    )


async def find_by_message_id(conn: DBConnection, dialogue_message_id: UUID) -> list[dict[str, Any]]:
    query = """--sql
    SELECT id, storage_key, mime_type, image_order
    FROM dialogue_message_images
    WHERE dialogue_message_id = $1
    ORDER BY image_order ASC
    """
    records = await conn.fetch(query, str(dialogue_message_id))
    return [dict(r) for r in records]


async def find_by_session_id(conn: DBConnection, dialogue_session_id: UUID) -> list[dict[str, Any]]:
    query = """--sql
    SELECT img.id, img.dialogue_message_id, img.storage_key, img.mime_type, img.image_order
    FROM dialogue_message_images img
    JOIN dialogue_messages msg ON msg.id = img.dialogue_message_id
    WHERE msg.dialogue_session_id = $1
    ORDER BY msg.message_order ASC, img.image_order ASC
    """
    records = await conn.fetch(query, str(dialogue_session_id))
    return [dict(r) for r in records]


async def find_in_session(conn: DBConnection, dialogue_session_id: UUID, image_id: UUID) -> dict[str, Any] | None:
    """配信エンドポイント用。画像が当該セッション配下に属することを保証して取得する。"""
    query = """--sql
    SELECT img.storage_key, img.mime_type
    FROM dialogue_message_images img
    JOIN dialogue_messages msg ON msg.id = img.dialogue_message_id
    WHERE img.id = $1 AND msg.dialogue_session_id = $2
    """
    record = await conn.fetchrow(query, str(image_id), str(dialogue_session_id))
    return dict(record) if record else None
