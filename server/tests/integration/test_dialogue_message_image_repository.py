from uuid import UUID, uuid4

import asyncpg
import pytest

from repositories import (
    dialogue_message_image_repository,
    dialogue_message_repository,
    dialogue_session_repository,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _seed_message(conn: asyncpg.Connection, user_id: str) -> tuple[UUID, UUID]:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=conn, session_id=session_id, user_id=user_id, session_type="learning", graph_version=2
    )
    message = await dialogue_message_repository.insert(conn, session_id, "user", "見て", 1)
    assert message is not None
    return session_id, message["id"]


async def test_insert_many_then_find_by_message_id(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    _, message_id = await _seed_message(db_conn, test_user["id"])

    await dialogue_message_image_repository.insert_many(
        db_conn, message_id, [("k0.png", "image/png"), ("k1.jpg", "image/jpeg")]
    )

    images = await dialogue_message_image_repository.find_by_message_id(db_conn, message_id)
    assert [img["image_order"] for img in images] == [0, 1]
    assert images[0]["storage_key"] == "k0.png"
    assert images[1]["mime_type"] == "image/jpeg"


async def test_insert_many_empty_is_noop(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    _, message_id = await _seed_message(db_conn, test_user["id"])

    await dialogue_message_image_repository.insert_many(db_conn, message_id, [])

    assert await dialogue_message_image_repository.find_by_message_id(db_conn, message_id) == []


async def test_find_in_session_scopes_to_session(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id, message_id = await _seed_message(db_conn, test_user["id"])
    await dialogue_message_image_repository.insert_many(db_conn, message_id, [("k0.webp", "image/webp")])
    image = (await dialogue_message_image_repository.find_by_message_id(db_conn, message_id))[0]

    found = await dialogue_message_image_repository.find_in_session(db_conn, session_id, image["id"])
    assert found is not None
    assert found["storage_key"] == "k0.webp"

    other_session = uuid4()
    assert await dialogue_message_image_repository.find_in_session(db_conn, other_session, image["id"]) is None


async def test_images_cascade_delete_with_message(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id, message_id = await _seed_message(db_conn, test_user["id"])
    await dialogue_message_image_repository.insert_many(db_conn, message_id, [("k0.png", "image/png")])

    await dialogue_message_repository.delete_last_n(db_conn, session_id, 1)

    assert await dialogue_message_image_repository.find_by_message_id(db_conn, message_id) == []
