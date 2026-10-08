from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import create_checkpoint, empty_checkpoint
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from evals.tools import capture_feedback
from graph.prompts.feedback import FEEDBACK_PROMPT_FINGERPRINT
from graph.version import GRAPH_VERSION
from repositories import dialogue_session_repository, feedback_repository, note_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://curigor:localdev@localhost:5433/curigor_test",
)

_ASPECT_MAP = {"root": "プロセス", "aspects": [{"name": "実行単位", "summary": "s", "coverage": "covered"}]}
_DEPTH_MAP = {"aspects": [{"id": "a1", "name": "実行単位", "is_core": True}]}
_MAP_COVERED = [{"aspect_id": "a1", "reached_stage": "defined"}]


@pytest_asyncio.fixture(loop_scope="session")
async def checkpointer() -> AsyncGenerator[AsyncPostgresSaver]:
    async with AsyncPostgresSaver.from_conn_string(TEST_DATABASE_URL) as saver:
        await saver.setup()
        yield saver


async def _put_final_state(saver: AsyncPostgresSaver, session_id: UUID, values: dict[str, Any]) -> None:
    config: RunnableConfig = {"configurable": {"thread_id": str(session_id), "checkpoint_ns": ""}}
    base = empty_checkpoint()
    base["channel_values"] = values
    base["channel_versions"] = {channel: f"{1:032d}.0" for channel in values}
    await saver.aput(config, create_checkpoint(base, None, 1), {"source": "loop", "step": 1}, base["channel_versions"])


async def _seed(
    conn: asyncpg.Connection,
    user_id: str,
    *,
    session_type: str = "learning",
    level: str = "medium",
) -> tuple[UUID, UUID]:
    session_id = uuid4()
    note_id = uuid4()
    await dialogue_session_repository.create(
        conn=conn, session_id=session_id, user_id=user_id, session_type=session_type, graph_version=GRAPH_VERSION
    )
    await note_repository.insert(
        conn,
        note_id=note_id,
        user_id=user_id,
        topic="プロセス",
        content="## 学んだこと\n- 実行単位",
        summary="s",
        aspect_map=json.dumps(_ASPECT_MAP, ensure_ascii=False),
    )
    await feedback_repository.insert(
        conn,
        note_id=note_id,
        dialogue_session_id=session_id,
        understanding_level=level,
        strength="実行単位を説明できた\n例を挙げた",
        improvements="メモリ空間",
        improvement_items=json.dumps([{"text": "メモリ空間", "aspect_id": "a1"}], ensure_ascii=False),
    )
    return session_id, note_id


def _map_values() -> dict[str, Any]:
    return {
        "topic": "プロセス",
        "intake_complete": True,
        "depth_map": _DEPTH_MAP,
        "map_covered": _MAP_COVERED,
        "messages": [HumanMessage(content="プロセス"), AIMessage(content="何を知っていますか？")],
    }


async def test_collect_builds_a_record_from_the_feedback_and_the_final_state(
    db_conn: asyncpg.Connection, test_user: dict[str, str], checkpointer: AsyncPostgresSaver
) -> None:
    session_id, note_id = await _seed(db_conn, test_user["id"])
    await _put_final_state(checkpointer, session_id, _map_values())
    rows = await capture_feedback.fetch_rows(db_conn, "WHERE f.dialogue_session_id = $1", session_id)

    records, warnings = await capture_feedback.collect(checkpointer, rows)

    assert warnings == []
    [record] = records
    assert record["id"].endswith("__feedback")
    assert record["session_type"] == "learning"
    assert record["note_id"] == str(note_id)
    assert record["meta"]["route"] == "map"
    assert record["meta"]["prompt_fingerprint"] == FEEDBACK_PROMPT_FINGERPRINT
    assert set(record["meta"]["models"]) == {"analyze-dialogue", "generate-feedback-scores"}
    assert record["input"] == {
        "topic": "プロセス",
        "conversation": [
            {"role": "human", "content": "プロセス"},
            {"role": "ai", "content": "何を知っていますか？"},
        ],
        "note_text": "トピック: プロセス\n\n## 学んだこと\n- 実行単位",
        "aspect_map": _ASPECT_MAP,
        "depth_map": _DEPTH_MAP,
        "map_covered": _MAP_COVERED,
    }
    assert record["output"] == {
        "understanding_level": "medium",
        "strengths": ["実行単位を説明できた", "例を挙げた"],
        "improvements": [{"text": "メモリ空間", "aspect_id": "a1"}],
    }
    assert record["human_level"] is None


async def test_collect_skips_a_feedback_whose_note_was_rewritten_by_a_later_review(
    db_conn: asyncpg.Connection, test_user: dict[str, str], checkpointer: AsyncPostgresSaver
) -> None:
    session_id, note_id = await _seed(db_conn, test_user["id"])
    review_id = uuid4()
    await dialogue_session_repository.create(
        conn=db_conn, session_id=review_id, user_id=test_user["id"], session_type="review", graph_version=GRAPH_VERSION
    )
    await feedback_repository.insert(
        db_conn,
        note_id=note_id,
        dialogue_session_id=review_id,
        understanding_level="high",
        strength="s",
        improvements="i",
    )
    await _put_final_state(checkpointer, session_id, _map_values())
    rows = await capture_feedback.fetch_rows(db_conn, "WHERE f.dialogue_session_id = $1", session_id)

    records, warnings = await capture_feedback.collect(checkpointer, rows)

    assert records == []
    assert "後の復習" in warnings[0]


async def test_collect_skips_a_session_without_a_checkpoint(
    db_conn: asyncpg.Connection, test_user: dict[str, str], checkpointer: AsyncPostgresSaver
) -> None:
    session_id, _ = await _seed(db_conn, test_user["id"])
    rows = await capture_feedback.fetch_rows(db_conn, "WHERE f.dialogue_session_id = $1", session_id)

    records, warnings = await capture_feedback.collect(checkpointer, rows)

    assert records == []
    assert "チェックポイント" in warnings[0]


async def test_review_record_uses_the_note_topic_and_has_no_route(
    db_conn: asyncpg.Connection, test_user: dict[str, str], checkpointer: AsyncPostgresSaver
) -> None:
    session_id, _ = await _seed(db_conn, test_user["id"], session_type="review")
    await _put_final_state(checkpointer, session_id, {"topic": "別名", "messages": [HumanMessage(content="プロセス")]})
    rows = await capture_feedback.fetch_rows(db_conn, "WHERE f.dialogue_session_id = $1", session_id)

    [record], _ = await capture_feedback.collect(checkpointer, rows)

    assert record["input"]["topic"] == "プロセス"
    assert "route" not in record["meta"]
    assert "depth_map" not in record["input"]


async def test_cli_appends_then_skips_on_rerun(
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    checkpointer: AsyncPostgresSaver,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_id, _ = await _seed(db_conn, test_user["id"])
    await _put_final_state(checkpointer, session_id, _map_values())
    out = tmp_path / "feedback.jsonl"
    args = ["--session-id", str(session_id), "--out", str(out)]

    assert await capture_feedback.run(capture_feedback.parse_args(args), TEST_DATABASE_URL) == 0
    assert await capture_feedback.run(capture_feedback.parse_args(args), TEST_DATABASE_URL) == 0

    assert len(out.read_text(encoding="utf-8").splitlines()) == 1
    assert "skipped 1 existing" in capsys.readouterr().out


async def test_cli_lists_feedbacks_and_marks_captured_sessions(
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    checkpointer: AsyncPostgresSaver,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_id, _ = await _seed(db_conn, test_user["id"])
    await _put_final_state(checkpointer, session_id, _map_values())
    out = tmp_path / "feedback.jsonl"
    await capture_feedback.run(capture_feedback.parse_args(["--recent", "--out", str(out)]), TEST_DATABASE_URL)
    capsys.readouterr()

    args = capture_feedback.parse_args(["--list", "--out", str(out)])
    assert await capture_feedback.run(args, TEST_DATABASE_URL) == 0

    line = next(line for line in capsys.readouterr().out.splitlines() if str(session_id) in line)
    assert "captured" in line


async def test_cli_reports_an_unknown_session(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    args = ["--session-id", str(uuid4()), "--out", str(tmp_path / "f.jsonl")]

    assert await capture_feedback.run(capture_feedback.parse_args(args), TEST_DATABASE_URL) == 1
    assert "フィードバックのある" in capsys.readouterr().err
