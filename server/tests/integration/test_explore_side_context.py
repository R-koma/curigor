from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import asyncpg
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from core import database
from graph.nodes._explore_dialogue import ExploreTurnPlan, respond_explore
from graph.state import LearningState
from repositories import dialogue_message_repository, dialogue_session_repository, side_question_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _plan() -> ExploreTurnPlan:
    return ExploreTurnPlan(
        user_intent="question", topic="", terms=[], question_summary="", wrap_up=False, end_confirmation=None
    )


async def _respond(state: dict[str, Any]) -> str:
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="答え", id="ai-1"))
    with (
        patch("graph.nodes._explore_dialogue.llm", mock_llm),
        patch("graph.nodes._explore_dialogue.load_image_blocks", new=AsyncMock(return_value=[])),
    ):
        await respond_explore(cast(LearningState, state), _plan())
    return str(mock_llm.ainvoke.call_args.args[0][0].content)


def _state(session_id: str) -> dict[str, Any]:
    return {
        "user_id": "u",
        "dialogue_session_id": session_id,
        "messages": [HumanMessage("インデックスとは"), AIMessage("索引です"), HumanMessage("続き")],
        "topic": "インデックス",
        "turn_count": 1,
        "should_generate_note": False,
        "session_type": "explore",
    }


async def test_respond_explore_reads_side_questions_for_session(
    db_conn: asyncpg.Connection, test_pool: asyncpg.Pool, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(database, "_pool", test_pool)
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=db_conn, session_id=session_id, user_id=test_user["id"], session_type="explore", graph_version=2
    )
    answer = await dialogue_message_repository.insert(db_conn, session_id, "assistant", "索引は B木 で持つ", 1)
    assert answer is not None
    thread = await side_question_repository.create(
        db_conn,
        dialogue_session_id=session_id,
        parent_id=None,
        anchor_message_id=answer["id"],
        anchor_side_message_id=None,
        quote="B木",
        occurrence=0,
        depth=0,
    )
    await side_question_repository.add_message(db_conn, thread["id"], "user", "B木とは？")
    await side_question_repository.add_message(db_conn, thread["id"], "assistant", "枝分かれの多い木")

    prompt = await _respond(_state(str(session_id)))

    assert "## 横で尋ねられたこと" in prompt
    assert "「B木」" in prompt
    assert "枝分かれの多い木" in prompt


async def test_respond_explore_without_side_questions_has_no_section(
    db_conn: asyncpg.Connection, test_pool: asyncpg.Pool, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(database, "_pool", test_pool)
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=db_conn, session_id=session_id, user_id=test_user["id"], session_type="explore", graph_version=2
    )

    prompt = await _respond(_state(str(session_id)))

    assert "横で尋ねられたこと" not in prompt


async def test_respond_explore_continues_when_reading_side_questions_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    async def broken_pool() -> Any:
        raise OSError("db down")

    monkeypatch.setattr("graph.nodes._explore_dialogue.get_pool", broken_pool)

    prompt = await _respond(_state(str(uuid4())))

    assert "横で尋ねられたこと" not in prompt
