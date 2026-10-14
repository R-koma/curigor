from uuid import UUID, uuid4

import asyncpg
import pytest

from repositories import dialogue_session_repository, note_repository, study_memo_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")

_OVERVIEW = [{"aspect_id": "a1", "name": "比較", "summary": "真ん中と比べる", "is_core": True}]
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
        overview=_OVERVIEW,
        glossary=_GLOSSARY,
        questions=_QUESTIONS,
        depth_map=_MAP,
    )

    found = await study_memo_repository.find_by_id(db_conn, memo_id, user_id)
    assert found is not None
    assert found["topic"] == "二分探索"
    assert found["overview"] == _OVERVIEW
    assert found["glossary"] == _GLOSSARY
    assert found["questions"] == _QUESTIONS
    assert found["depth_map"] == _MAP


async def test_other_users_cannot_read_the_memo(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    session_id = await _explore_session(db_conn, user_id)
    memo_id = await study_memo_repository.insert(
        db_conn,
        user_id=user_id,
        dialogue_session_id=session_id,
        topic="二分探索",
        source="",
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
