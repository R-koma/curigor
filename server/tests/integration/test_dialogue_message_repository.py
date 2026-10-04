import json
from uuid import uuid4

import asyncpg
import pytest

from repositories import dialogue_message_repository, dialogue_session_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_insert_with_duplicate_client_message_id_is_noop(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = uuid4()
    client_message_id = uuid4()
    await dialogue_session_repository.create(
        conn=db_conn, session_id=session_id, user_id=test_user["id"], session_type="learning", graph_version=2
    )

    first = await dialogue_message_repository.insert(
        db_conn, session_id, "user", "こんにちは", 1, client_message_id=client_message_id
    )
    second = await dialogue_message_repository.insert(
        db_conn, session_id, "user", "こんにちは", 2, client_message_id=client_message_id
    )

    assert first is not None
    assert second is None
    rows = await dialogue_message_repository.find_by_session_id(db_conn, session_id)
    assert len(rows) == 1


async def test_insert_without_client_message_id_never_conflicts(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=db_conn, session_id=session_id, user_id=test_user["id"], session_type="learning", graph_version=2
    )

    first = await dialogue_message_repository.insert(db_conn, session_id, "assistant", "やあ", 1)
    second = await dialogue_message_repository.insert(db_conn, session_id, "assistant", "やあ", 2)

    assert first is not None
    assert second is not None
    rows = await dialogue_message_repository.find_by_session_id(db_conn, session_id)
    assert len(rows) == 2


async def test_insert_persists_intake_card(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=db_conn, session_id=session_id, user_id=test_user["id"], session_type="learning", graph_version=2
    )
    card = json.dumps({"questions": []})

    await dialogue_message_repository.insert(db_conn, session_id, "assistant", "lead", 2, intake_card=card)
    await dialogue_message_repository.insert(db_conn, session_id, "user", "回答", 3)

    rows = await dialogue_message_repository.find_by_session_id(db_conn, session_id)
    assert json.loads(rows[0]["intake_card"]) == {"questions": []}
    assert rows[1]["intake_card"] is None


async def test_insert_persists_intake_answers(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=db_conn, session_id=session_id, user_id=test_user["id"], session_type="learning", graph_version=2
    )
    answers = json.dumps({"purpose": "", "source": ["入門書"], "prior_knowledge": "初めて学ぶ"})

    await dialogue_message_repository.insert(db_conn, session_id, "user", "教材: 入門書", 3, intake_answers=answers)
    await dialogue_message_repository.insert(db_conn, session_id, "user", "自由文の返信", 4)

    rows = await dialogue_message_repository.find_by_session_id(db_conn, session_id)
    assert json.loads(rows[0]["intake_answers"]) == {
        "purpose": "",
        "source": ["入門書"],
        "prior_knowledge": "初めて学ぶ",
    }
    assert rows[1]["intake_answers"] is None


async def test_insert_records_voice_input_with_the_raw_transcript(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=db_conn, session_id=session_id, user_id=test_user["id"], session_type="learning", graph_version=2
    )

    message = await dialogue_message_repository.insert(
        db_conn,
        session_id,
        "user",
        "二分探索は半分に絞る手法です",
        1,
        input_mode="voice",
        raw_transcript="二分探索は半分にしぼる手法です",
    )

    assert message is not None
    assert message["input_mode"] == "voice"
    assert message["raw_transcript"] == "二分探索は半分にしぼる手法です"


async def test_insert_defaults_to_text_input(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=db_conn, session_id=session_id, user_id=test_user["id"], session_type="learning", graph_version=2
    )

    message = await dialogue_message_repository.insert(db_conn, session_id, "user", "手で書いた", 1)

    assert message is not None
    assert message["input_mode"] == "text"
    assert message["raw_transcript"] is None


async def test_insert_records_auto_sent_voice_input(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=db_conn, session_id=session_id, user_id=test_user["id"], session_type="learning", graph_version=2
    )

    message = await dialogue_message_repository.insert(
        db_conn, session_id, "user", "説明します", 1, input_mode="voice_auto", raw_transcript="せつめいします"
    )

    assert message is not None
    assert message["input_mode"] == "voice_auto"


async def test_insert_rejects_an_unknown_input_mode(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=db_conn, session_id=session_id, user_id=test_user["id"], session_type="learning", graph_version=2
    )

    with pytest.raises(asyncpg.CheckViolationError):
        await dialogue_message_repository.insert(db_conn, session_id, "user", "x", 1, input_mode="whisper")
