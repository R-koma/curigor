import uuid

import asyncpg
import pytest

from repositories import (
    collection_synthesis_repository,
    note_collection_repository,
    note_repository,
    note_revision_repository,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _upsert(conn: asyncpg.Connection, collection_id: uuid.UUID, content: str) -> dict[str, object]:
    return await collection_synthesis_repository.upsert(
        conn,
        collection_id=collection_id,
        content=content,
        connections=[{"id": "c1", "title": "つながり", "note_ids": [], "explanation": "e", "question": "q"}],
        contradictions=[],
        gaps=["割り込み"],
        source_notes=[{"note_id": "n", "content_hash": "h"}],
    )


async def test_upsert_replaces_the_previous_draft(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    collection = await note_collection_repository.get_or_create(db_conn, test_user["id"], "Linuxのしくみ")
    await _upsert(db_conn, collection["id"], "古い")
    await _upsert(db_conn, collection["id"], "新しい")

    found = await collection_synthesis_repository.find_by_collection_id(db_conn, collection["id"], test_user["id"])

    assert found is not None
    assert found["content"] == "新しい"
    assert found["connections"][0]["title"] == "つながり"
    assert found["gaps"] == ["割り込み"]


async def test_find_excludes_other_users(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    collection = await note_collection_repository.get_or_create(db_conn, test_user["id"], "Linuxのしくみ")
    await _upsert(db_conn, collection["id"], "本文")

    assert await collection_synthesis_repository.find_by_collection_id(db_conn, collection["id"], "other") is None


async def test_find_contents_by_collection_id_includes_revisions_in_order(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    collection = await note_collection_repository.get_or_create(db_conn, user_id, "Linuxのしくみ")
    note_id = uuid.uuid4()
    await note_repository.insert(db_conn, note_id=note_id, user_id=user_id, topic="T", content="base", summary="s")
    await note_repository.set_collection(db_conn, note_id, user_id, collection["id"])
    session_id = uuid.uuid4()
    await db_conn.execute(
        "INSERT INTO dialogue_sessions (id, user_id, session_type, status) VALUES ($1, $2, 'review', 'completed')",
        session_id,
        user_id,
    )
    await note_revision_repository.insert(db_conn, note_id=note_id, dialogue_session_id=session_id, content="1")
    await note_revision_repository.insert(db_conn, note_id=note_id, dialogue_session_id=session_id, content="2")

    rows = await note_repository.find_contents_by_collection_id(db_conn, collection["id"], user_id)

    assert rows == [{"id": note_id, "topic": "T", "content": "base", "revisions": ["1", "2"]}]
