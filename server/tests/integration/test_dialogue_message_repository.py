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
