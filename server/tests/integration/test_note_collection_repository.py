import uuid

import asyncpg
import pytest

from repositories import note_collection_repository, note_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _insert_note(conn: asyncpg.Connection, user_id: str, topic: str = "T") -> uuid.UUID:
    note_id = uuid.uuid4()
    await note_repository.insert(conn, note_id=note_id, user_id=user_id, topic=topic, content="c", summary="s")
    return note_id


async def test_get_or_create_returns_the_existing_collection_for_the_same_name(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    first = await note_collection_repository.get_or_create(db_conn, test_user["id"], "Linuxのしくみ")
    second = await note_collection_repository.get_or_create(db_conn, test_user["id"], "Linuxのしくみ")

    assert first["id"] == second["id"]
    assert len(await note_collection_repository.find_by_user_id(db_conn, test_user["id"])) == 1


async def test_find_by_user_id_counts_notes(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    collection = await note_collection_repository.get_or_create(db_conn, user_id, "Linuxのしくみ")
    note_id = await _insert_note(db_conn, user_id)
    await note_repository.set_collection(db_conn, note_id, user_id, collection["id"])
    await note_collection_repository.get_or_create(db_conn, user_id, "空のテーマ")

    counts = {c["name"]: c["note_count"] for c in await note_collection_repository.find_by_user_id(db_conn, user_id)}

    assert counts == {"Linuxのしくみ": 1, "空のテーマ": 0}


async def test_find_by_id_excludes_other_users(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    collection = await note_collection_repository.get_or_create(db_conn, test_user["id"], "Linuxのしくみ")

    assert await note_collection_repository.find_by_id(db_conn, collection["id"], "someone-else") is None


async def test_rename_to_an_existing_name_raises(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    await note_collection_repository.get_or_create(db_conn, user_id, "A")
    b = await note_collection_repository.get_or_create(db_conn, user_id, "B")

    with pytest.raises(asyncpg.UniqueViolationError):
        await note_collection_repository.rename(db_conn, b["id"], user_id, "A")


async def test_delete_keeps_the_notes_and_unlinks_them(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    collection = await note_collection_repository.get_or_create(db_conn, user_id, "Linuxのしくみ")
    note_id = await _insert_note(db_conn, user_id)
    await note_repository.set_collection(db_conn, note_id, user_id, collection["id"])

    assert await note_collection_repository.delete(db_conn, collection["id"], user_id) is True

    note = await note_repository.find_by_id(db_conn, note_id, user_id)
    assert note is not None
    assert note["collection_id"] is None


async def test_set_collection_clears_the_suggestion(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    note_id = uuid.uuid4()
    await note_repository.insert(
        db_conn,
        note_id=note_id,
        user_id=user_id,
        topic="T",
        content="c",
        summary="s",
        suggested_collection="Linuxのしくみ",
    )
    collection = await note_collection_repository.get_or_create(db_conn, user_id, "Linuxのしくみ")

    assert await note_repository.set_collection(db_conn, note_id, user_id, collection["id"]) is True

    note = await note_repository.find_by_id(db_conn, note_id, user_id)
    assert note is not None
    assert note["collection_id"] == collection["id"]
    assert note["suggested_collection"] is None


async def test_clear_suggested_collection(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    note_id = uuid.uuid4()
    await note_repository.insert(
        db_conn, note_id=note_id, user_id=user_id, topic="T", content="c", summary="s", suggested_collection="X"
    )

    assert await note_repository.clear_suggested_collection(db_conn, note_id, user_id) is True

    note = await note_repository.find_by_id(db_conn, note_id, user_id)
    assert note is not None
    assert note["suggested_collection"] is None


async def test_find_by_collection_id_orders_by_creation(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    collection = await note_collection_repository.get_or_create(db_conn, user_id, "Linuxのしくみ")
    first = await _insert_note(db_conn, user_id, topic="プロセス")
    second = await _insert_note(db_conn, user_id, topic="システムコール")
    for note_id in (second, first):
        await note_repository.set_collection(db_conn, note_id, user_id, collection["id"])

    notes = await note_repository.find_by_collection_id(db_conn, collection["id"], user_id)

    assert [n["topic"] for n in notes] == ["プロセス", "システムコール"]
    assert notes[0]["review_count"] == 0
