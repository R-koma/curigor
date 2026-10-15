import uuid

import asyncpg
import pytest

from repositories import note_repository, note_revision_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _insert_dialogue_session(conn: asyncpg.Connection, user_id: str) -> uuid.UUID:
    session_id = uuid.uuid4()
    await conn.execute(
        """--sql
        INSERT INTO dialogue_sessions (id, user_id, session_type, status)
        VALUES ($1, $2, 'review', 'completed')
        """,
        session_id,
        user_id,
    )
    return session_id


async def test_insert_and_find_by_note_id(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    note_id = uuid.uuid4()
    user_id = test_user["id"]
    await note_repository.insert(db_conn, note_id=note_id, user_id=user_id, topic="T", content="base", summary="s")
    session_id = await _insert_dialogue_session(db_conn, user_id)

    created = await note_revision_repository.insert(
        db_conn, note_id=note_id, dialogue_session_id=session_id, content="- 追記1"
    )
    assert created["content"] == "- 追記1"

    revisions = await note_revision_repository.find_by_note_id(db_conn, note_id=note_id, user_id=user_id)
    assert len(revisions) == 1
    assert revisions[0]["content"] == "- 追記1"


async def test_find_by_note_id_orders_by_created_at(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    note_id = uuid.uuid4()
    user_id = test_user["id"]
    await note_repository.insert(db_conn, note_id=note_id, user_id=user_id, topic="T", content="base", summary="s")
    session_id = await _insert_dialogue_session(db_conn, user_id)

    await note_revision_repository.insert(db_conn, note_id=note_id, dialogue_session_id=session_id, content="古い追記")
    await note_revision_repository.insert(
        db_conn, note_id=note_id, dialogue_session_id=session_id, content="新しい追記"
    )

    revisions = await note_revision_repository.find_by_note_id(db_conn, note_id=note_id, user_id=user_id)
    assert [r["content"] for r in revisions] == ["古い追記", "新しい追記"]


async def test_find_by_note_id_excludes_other_user(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    note_id = uuid.uuid4()
    user_id = test_user["id"]
    await note_repository.insert(db_conn, note_id=note_id, user_id=user_id, topic="T", content="base", summary="s")
    session_id = await _insert_dialogue_session(db_conn, user_id)
    await note_revision_repository.insert(db_conn, note_id=note_id, dialogue_session_id=session_id, content="追記")

    revisions = await note_revision_repository.find_by_note_id(db_conn, note_id=note_id, user_id="other-user-id")
    assert revisions == []


async def test_find_by_note_id_returns_empty_when_none(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    note_id = uuid.uuid4()
    await note_repository.insert(
        db_conn, note_id=note_id, user_id=test_user["id"], topic="T", content="base", summary="s"
    )

    revisions = await note_revision_repository.find_by_note_id(db_conn, note_id=note_id, user_id=test_user["id"])
    assert revisions == []


async def test_insert_saves_the_prompt_fingerprint(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    note_id = uuid.uuid4()
    user_id = test_user["id"]
    await note_repository.insert(db_conn, note_id=note_id, user_id=user_id, topic="T", content="base", summary="s")
    session_id = await _insert_dialogue_session(db_conn, user_id)

    created = await note_revision_repository.insert(
        db_conn, note_id=note_id, dialogue_session_id=session_id, content="- 追記", prompt_fingerprint="dddddddddddd"
    )

    stored = await db_conn.fetchval("SELECT prompt_fingerprint FROM note_revisions WHERE id = $1", created["id"])
    assert stored == "dddddddddddd"
