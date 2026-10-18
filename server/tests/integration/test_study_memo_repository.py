from datetime import timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest

from repositories import dialogue_session_repository, note_repository, study_memo_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")

_OVERVIEW = [
    {
        "aspect_id": "a1",
        "name": "比較",
        "summary": "真ん中と比べる",
        "is_core": True,
        "question_indices": [0],
        "term_indices": [0],
    }
]
_GLOSSARY = [{"term": "計算量", "reading": "けいさんりょう", "meaning": "処理にかかる手間の目安"}]
_QUESTIONS = [{"question": "なぜ並んでいる必要があるのか", "answer": "半分を捨てる判断ができないから"}]
_MAP = {"topic": "二分探索", "aspects": []}


async def _explore_session(db_conn: asyncpg.Connection, user_id: str) -> UUID:
    session_id = uuid4()
    await dialogue_session_repository.create(
        db_conn, session_id=session_id, user_id=user_id, session_type="explore", graph_version=4, topic="二分探索"
    )
    return session_id


async def test_insert_and_find_by_id_decodes_json(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    session_id = await _explore_session(db_conn, user_id)

    memo_id = await study_memo_repository.insert(
        db_conn,
        user_id=user_id,
        dialogue_session_id=session_id,
        topic="二分探索",
        source="",
        summary="真ん中と比べて半分を捨てる探し方を教わった",
        overview=_OVERVIEW,
        glossary=_GLOSSARY,
        questions=_QUESTIONS,
        depth_map=_MAP,
    )

    found = await study_memo_repository.find_by_id(db_conn, memo_id, user_id)
    assert found is not None
    assert found["topic"] == "二分探索"
    assert found["summary"] == "真ん中と比べて半分を捨てる探し方を教わった"
    assert found["overview"] == _OVERVIEW
    assert found["glossary"] == _GLOSSARY
    assert found["questions"] == _QUESTIONS
    assert found["depth_map"] == _MAP


async def test_memo_inserted_before_the_summary_column_reads_an_empty_summary(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    session_id = await _explore_session(db_conn, user_id)
    memo_id = await db_conn.fetchval(
        """--sql
        INSERT INTO study_memos (user_id, dialogue_session_id, topic, source, overview, glossary, questions, depth_map)
        VALUES ($1, $2, '二分探索', '', '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '{}'::jsonb)
        RETURNING id
        """,
        user_id,
        str(session_id),
    )

    found = await study_memo_repository.find_by_id(db_conn, memo_id, user_id)
    assert found is not None
    assert found["summary"] == ""


async def test_other_users_cannot_read_the_memo(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    session_id = await _explore_session(db_conn, user_id)
    memo_id = await study_memo_repository.insert(
        db_conn,
        user_id=user_id,
        dialogue_session_id=session_id,
        topic="二分探索",
        source="",
        summary="",
        overview=[],
        glossary=[],
        questions=[],
        depth_map=_MAP,
    )

    assert await study_memo_repository.find_by_id(db_conn, memo_id, "other-user") is None
    assert await study_memo_repository.find_by_session_id(db_conn, uuid4(), user_id) is None
    assert await study_memo_repository.find_by_user_id(db_conn, "other-user") == []


async def test_find_by_session_and_list_newest_first(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    first_session = await _explore_session(db_conn, user_id)
    second_session = await _explore_session(db_conn, user_id)
    for session_id, topic in ((first_session, "二分探索"), (second_session, "統計学")):
        await study_memo_repository.insert(
            db_conn,
            user_id=user_id,
            dialogue_session_id=session_id,
            topic=topic,
            source="入門書",
            summary="",
            overview=[],
            glossary=[],
            questions=[],
            depth_map=_MAP,
        )

    by_session = await study_memo_repository.find_by_session_id(db_conn, second_session, user_id)
    assert by_session is not None and by_session["topic"] == "統計学"
    listed = await study_memo_repository.find_by_user_id(db_conn, user_id)
    assert [m["topic"] for m in listed] == ["統計学", "二分探索"]


async def _memo(db_conn: asyncpg.Connection, user_id: str) -> UUID:
    session_id = await _explore_session(db_conn, user_id)
    return await study_memo_repository.insert(
        db_conn,
        user_id=user_id,
        dialogue_session_id=session_id,
        topic="二分探索",
        source="",
        summary="",
        overview=[],
        glossary=[],
        questions=[],
        depth_map=_MAP,
    )


async def _learning_session(db_conn: asyncpg.Connection, user_id: str, memo_id: UUID) -> UUID:
    session_id = uuid4()
    await dialogue_session_repository.create(
        db_conn,
        session_id=session_id,
        user_id=user_id,
        session_type="learning",
        graph_version=4,
        study_memo_id=memo_id,
    )
    return session_id


async def _handed_over(db_conn: asyncpg.Connection, user_id: str) -> bool:
    [row] = await study_memo_repository.find_by_user_id(db_conn, user_id)
    return bool(row["handed_over"])


async def test_a_memo_is_not_handed_over_before_a_learning_session_makes_a_note(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    memo_id = await _memo(db_conn, user_id)
    assert await _handed_over(db_conn, user_id) is False

    session_id = await _learning_session(db_conn, user_id, memo_id)
    assert await _handed_over(db_conn, user_id) is False

    note_id = uuid4()
    await note_repository.insert(db_conn, note_id, user_id, "二分探索", "本文", "要約")
    await dialogue_session_repository.update_note_id(db_conn, session_id, note_id)
    assert await _handed_over(db_conn, user_id) is True


async def test_a_learning_session_that_ended_without_a_note_does_not_hand_the_memo_over(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    memo_id = await _memo(db_conn, user_id)
    session_id = await _learning_session(db_conn, user_id, memo_id)

    await dialogue_session_repository.update_status(db_conn, session_id, "completed")

    assert await _handed_over(db_conn, user_id) is False


async def test_list_carries_the_aspects_and_counts_the_terms_and_questions(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    session_id = await _explore_session(db_conn, user_id)
    overview = [{"aspect_id": "a", "name": "比較", "summary": "s", "is_core": True}]
    await study_memo_repository.insert(
        db_conn,
        user_id=user_id,
        dialogue_session_id=session_id,
        topic="二分探索",
        source="",
        summary="",
        overview=overview,
        glossary=[
            {"term": "計算量", "reading": "けいさんりょう", "meaning": "手間"},
            {"term": "整列", "reading": "せいれつ", "meaning": "並べること"},
        ],
        questions=[{"question": "なぜ並べるのか", "answer": "半分を捨てるため"}],
        depth_map=_MAP,
    )

    [row] = await study_memo_repository.find_by_user_id(db_conn, user_id)

    assert row["overview"] == overview
    assert row["glossary_count"] == 2
    assert row["question_count"] == 1


async def test_update_writes_only_the_given_columns(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    session_id = await _explore_session(db_conn, user_id)
    memo_id = await study_memo_repository.insert(
        db_conn,
        user_id=user_id,
        dialogue_session_id=session_id,
        topic="二分探索",
        source="",
        summary="",
        overview=_OVERVIEW,
        glossary=_GLOSSARY,
        questions=_QUESTIONS,
        depth_map=_MAP,
    )

    updated = await study_memo_repository.update(
        db_conn, memo_id, user_id, {"summary": "書いた要約", "glossary": [], "overview": []}
    )

    assert updated is not None
    assert updated["summary"] == "書いた要約"
    assert updated["glossary"] == []
    assert updated["overview"] == []
    assert updated["questions"] == _QUESTIONS
    assert updated["topic"] == "二分探索"


async def test_delete_removes_the_memo_and_unlinks_the_learning_session(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    session_id = await _explore_session(db_conn, user_id)
    memo_id = await study_memo_repository.insert(
        db_conn,
        user_id=user_id,
        dialogue_session_id=session_id,
        topic="二分探索",
        source="",
        summary="",
        overview=_OVERVIEW,
        glossary=_GLOSSARY,
        questions=_QUESTIONS,
        depth_map=_MAP,
    )
    learning_id = uuid4()
    await dialogue_session_repository.create(
        db_conn,
        session_id=learning_id,
        user_id=user_id,
        session_type="learning",
        graph_version=4,
        topic="二分探索",
        study_memo_id=memo_id,
    )

    assert await study_memo_repository.delete(db_conn, memo_id, user_id) is True

    assert await study_memo_repository.find_by_id(db_conn, memo_id, user_id) is None
    assert await db_conn.fetchval("SELECT study_memo_id FROM dialogue_sessions WHERE id = $1", learning_id) is None
    assert await study_memo_repository.delete(db_conn, memo_id, user_id) is False


async def test_find_unorganized_returns_only_memos_without_a_summary_or_assignments(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    aspect = {"id": "a1", "name": "比較", "is_core": True}
    unassigned = [{"aspect_id": "a1", "name": "比較", "summary": "", "is_core": True}]

    async def insert(summary: str, overview: list[dict[str, object]], aspects: list[dict[str, object]]) -> UUID:
        return await study_memo_repository.insert(
            db_conn,
            user_id=user_id,
            dialogue_session_id=await _explore_session(db_conn, user_id),
            topic="二分探索",
            source="",
            summary=summary,
            overview=overview,
            glossary=_GLOSSARY,
            questions=_QUESTIONS,
            depth_map={"topic": "二分探索", "aspects": aspects},
        )

    target = await insert("", unassigned, [aspect])
    await insert("", _OVERVIEW, [aspect])
    await insert("要約あり", unassigned, [aspect])
    await insert("", [], [])

    found = await study_memo_repository.find_unorganized(db_conn)

    assert [m["id"] for m in found if m["user_id"] == user_id] == [target]


async def _note_with_feedback(db_conn: asyncpg.Connection, user_id: str) -> tuple[UUID, UUID]:
    note_id = uuid4()
    await note_repository.insert(db_conn, note_id, user_id, "ノートの話題", "本文", "要約")
    feedback_id = await _feedback(db_conn, note_id)
    return note_id, feedback_id


async def _feedback(db_conn: asyncpg.Connection, note_id: UUID, *, age: timedelta = timedelta()) -> UUID:
    return UUID(
        str(
            await db_conn.fetchval(
                """--sql
                INSERT INTO feedbacks (id, note_id, understanding_level, created_at)
                VALUES (gen_random_uuid(), $1, 'medium', NOW() + $2)
                RETURNING id
                """,
                note_id,
                age,
            )
        )
    )


async def _memo_from(
    db_conn: asyncpg.Connection, user_id: str, note_id: UUID, feedback_id: UUID, aspect_id: str | None = "a1"
) -> UUID:
    session_id = await _explore_session(db_conn, user_id)
    return await study_memo_repository.insert(
        db_conn,
        user_id=user_id,
        dialogue_session_id=session_id,
        topic="二分探索",
        source="",
        summary="",
        overview=[],
        glossary=[],
        questions=[],
        depth_map=_MAP,
        origin={
            "note_id": str(note_id),
            "feedback_id": str(feedback_id),
            "improvement_index": 1,
            "improvement": "境界の扱いが曖昧",
            "aspect_id": aspect_id,
        },
    )


async def test_insert_with_origin_is_listed_for_the_note(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    note_id, feedback_id = await _note_with_feedback(db_conn, user_id)

    memo_id = await _memo_from(db_conn, user_id, note_id, feedback_id)

    rows = await study_memo_repository.find_by_origin_note(db_conn, note_id, user_id)
    assert [r["id"] for r in rows] == [memo_id]
    assert rows[0]["origin_improvement_index"] == 1
    assert rows[0]["origin_aspect_id"] == "a1"
    detail = await study_memo_repository.find_by_id(db_conn, memo_id, user_id)
    assert detail is not None
    assert detail["origin_note_topic"] == "ノートの話題"
    assert detail["origin_improvement"] == "境界の扱いが曖昧"
    assert await study_memo_repository.find_priority_aspect_ids(db_conn, feedback_id, user_id) == ["a1"]


async def test_priority_aspect_ids_skip_memos_without_an_aspect_and_repeats(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    note_id, feedback_id = await _note_with_feedback(db_conn, user_id)
    await _memo_from(db_conn, user_id, note_id, feedback_id, "a1")
    await _memo_from(db_conn, user_id, note_id, feedback_id, "a1")
    await _memo_from(db_conn, user_id, note_id, feedback_id, None)

    assert await study_memo_repository.find_priority_aspect_ids(db_conn, feedback_id, user_id) == ["a1"]


async def test_find_by_origin_note_ignores_other_users(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    note_id, feedback_id = await _note_with_feedback(db_conn, user_id)
    await _memo_from(db_conn, user_id, note_id, feedback_id)

    assert await study_memo_repository.find_by_origin_note(db_conn, note_id, "someone-else") == []
    assert await study_memo_repository.find_priority_aspect_ids(db_conn, feedback_id, "someone-else") == []


async def test_deleting_the_note_keeps_the_memo_without_origin(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    note_id, feedback_id = await _note_with_feedback(db_conn, user_id)
    memo_id = await _memo_from(db_conn, user_id, note_id, feedback_id)

    await db_conn.execute("DELETE FROM notes WHERE id = $1", note_id)

    detail = await study_memo_repository.find_by_id(db_conn, memo_id, user_id)
    assert detail is not None
    assert detail["origin_note_id"] is None
    assert detail["origin_feedback_id"] is None
    assert detail["origin_note_topic"] is None


async def test_linked_memo_is_handed_over_after_a_newer_feedback(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    note_id, feedback_id = await _note_with_feedback(db_conn, user_id)
    await _memo_from(db_conn, user_id, note_id, feedback_id)
    await _feedback(db_conn, note_id, age=timedelta(hours=-1))
    assert await _handed_over(db_conn, user_id) is False

    await _feedback(db_conn, note_id, age=timedelta(hours=1))
    assert await _handed_over(db_conn, user_id) is True
