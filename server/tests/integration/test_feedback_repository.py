import json
import uuid

import asyncpg
import pytest

from repositories import feedback_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _insert_dialogue_session(conn: asyncpg.Connection, user_id: str, session_type: str = "review") -> uuid.UUID:
    session_id = uuid.uuid4()
    await conn.execute(
        """--sql
        INSERT INTO dialogue_sessions (id, user_id, session_type, status)
        VALUES ($1, $2, $3, 'completed')
        """,
        session_id,
        user_id,
        session_type,
    )
    return session_id


async def _insert_note(conn: asyncpg.Connection, user_id: str) -> uuid.UUID:
    note_id = uuid.uuid4()
    await conn.execute(
        """--sql
        INSERT INTO notes (id, user_id, topic, content, summary, status)
        VALUES ($1, $2, '統計学', 'original content', 'original summary', 'active')
        """,
        note_id,
        user_id,
    )
    return note_id


class TestFeedbackHistory:
    async def test_insert_keeps_every_evaluation_for_a_note(
        self, db_conn: asyncpg.Connection, test_user: dict[str, str]
    ) -> None:
        note_id = await _insert_note(db_conn, test_user["id"])
        learning = await _insert_dialogue_session(db_conn, test_user["id"], "learning")
        review = await _insert_dialogue_session(db_conn, test_user["id"], "review")

        await feedback_repository.insert(
            conn=db_conn,
            note_id=note_id,
            dialogue_session_id=learning,
            understanding_level="low",
            strength="s1",
            improvements="i1",
        )
        await feedback_repository.insert(
            conn=db_conn,
            note_id=note_id,
            dialogue_session_id=review,
            understanding_level="high",
            strength="s2",
            improvements="i2",
        )

        rows = await feedback_repository.find_by_note_id(db_conn, note_id, test_user["id"])

        assert [r["understanding_level"] for r in rows] == ["low", "high"]
        assert [r["session_type"] for r in rows] == ["learning", "review"]

    async def test_improvement_items_round_trip(self, db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
        note_id = await _insert_note(db_conn, test_user["id"])
        session = await _insert_dialogue_session(db_conn, test_user["id"], "learning")
        items = [{"text": "計算量が曖昧", "aspect_id": "a1"}, {"text": "前提の確認", "aspect_id": None}]

        await feedback_repository.insert(
            conn=db_conn,
            note_id=note_id,
            dialogue_session_id=session,
            understanding_level="low",
            strength="s",
            improvements="計算量が曖昧\n前提の確認",
            improvement_items=json.dumps(items, ensure_ascii=False),
        )

        (row,) = await feedback_repository.find_by_note_id(db_conn, note_id, test_user["id"])
        assert json.loads(row["improvement_items"]) == items

    async def test_improvement_items_default_to_null(
        self, db_conn: asyncpg.Connection, test_user: dict[str, str]
    ) -> None:
        note_id = await _insert_note(db_conn, test_user["id"])
        session = await _insert_dialogue_session(db_conn, test_user["id"], "learning")
        await feedback_repository.insert(
            conn=db_conn,
            note_id=note_id,
            dialogue_session_id=session,
            understanding_level="low",
            strength="s",
            improvements="i",
        )

        (row,) = await feedback_repository.find_by_note_id(db_conn, note_id, test_user["id"])
        assert row["improvement_items"] is None

    async def test_session_type_is_none_when_no_session_is_linked(
        self, db_conn: asyncpg.Connection, test_user: dict[str, str]
    ) -> None:
        note_id = await _insert_note(db_conn, test_user["id"])
        await db_conn.execute(
            """--sql
            INSERT INTO feedbacks (id, note_id, dialogue_session_id, understanding_level, strength, improvements)
            VALUES (gen_random_uuid(), $1, NULL, 'medium', 's', 'i')
            """,
            note_id,
        )

        rows = await feedback_repository.find_by_note_id(db_conn, note_id, test_user["id"])

        assert len(rows) == 1
        assert rows[0]["dialogue_session_id"] is None
        assert rows[0]["session_type"] is None
