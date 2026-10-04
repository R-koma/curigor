from uuid import uuid4

import asyncpg
import pytest

from repositories import dialogue_session_repository, note_collection_repository, synthesis_insight_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_insert_many_and_find_in_order(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    collection = await note_collection_repository.get_or_create(db_conn, user_id, "Linuxのしくみ")
    session_id = uuid4()
    await dialogue_session_repository.create(
        db_conn,
        session_id=session_id,
        user_id=user_id,
        session_type="synthesis",
        graph_version=4,
        collection_id=collection["id"],
        topic="Linuxのしくみ",
    )

    await synthesis_insight_repository.insert_many(
        db_conn,
        collection_id=collection["id"],
        dialogue_session_id=session_id,
        insights=[("コンテキストスイッチ", "説明1"), ("ページング", "説明2")],
    )

    found = await synthesis_insight_repository.find_by_collection_id(db_conn, collection["id"], user_id)
    assert [(i["connection_title"], i["content"]) for i in found] == [
        ("コンテキストスイッチ", "説明1"),
        ("ページング", "説明2"),
    ]
    assert await synthesis_insight_repository.find_by_collection_id(db_conn, collection["id"], "other") == []
