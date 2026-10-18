import json
import uuid

import asyncpg
import pytest

from repositories import review_plan_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _insert_note(conn: asyncpg.Connection, user_id: str) -> uuid.UUID:
    note_id = uuid.uuid4()
    await conn.execute(
        """--sql
        INSERT INTO notes (id, user_id, topic, content, summary, status)
        VALUES ($1, $2, '統計学', 'content', 'summary', 'active')
        """,
        note_id,
        user_id,
    )
    return note_id


async def test_upsert_then_find_returns_latest_points(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    note_id = await _insert_note(db_conn, test_user["id"])

    await review_plan_repository.upsert(db_conn, note_id, json.dumps([{"id": "p1"}]), "h1", "fp1")
    await review_plan_repository.upsert(db_conn, note_id, json.dumps([{"id": "p2"}]), "h2", "fp2")

    row = await review_plan_repository.find_by_note_id(db_conn, note_id, test_user["id"])
    assert row is not None
    assert row["points"] == [{"id": "p2"}]
    assert row["note_content_hash"] == "h2"
    assert row["prompt_fingerprint"] == "fp2"


async def test_find_returns_none_without_a_plan(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    note_id = await _insert_note(db_conn, test_user["id"])

    assert await review_plan_repository.find_by_note_id(db_conn, note_id, test_user["id"]) is None


async def test_find_by_note_id_hides_other_users_plan(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    note_id = await _insert_note(db_conn, test_user["id"])
    await review_plan_repository.upsert(db_conn, note_id, "[]", "h", "fp")

    assert await review_plan_repository.find_by_note_id(db_conn, note_id, "someone-else") is None


async def test_plan_is_deleted_with_its_note(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    note_id = await _insert_note(db_conn, test_user["id"])
    await review_plan_repository.upsert(db_conn, note_id, "[]", "h", "fp")

    await db_conn.execute("DELETE FROM notes WHERE id = $1", note_id)

    assert await db_conn.fetchval("SELECT count(*) FROM review_plans WHERE note_id = $1", note_id) == 0
