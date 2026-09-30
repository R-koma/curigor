"""capture の DB / チェックポイント経路を実 Postgres と実 AsyncPostgresSaver で検証する。"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import create_checkpoint, empty_checkpoint
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from evals.tools import capture
from graph.version import GRAPH_VERSION
from repositories import dialogue_message_repository, dialogue_session_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://learning_optimizer:localdev@localhost:5433/learning_optimizer_test",
)

_TOPIC = "プロセス"
_TURN1_OUTPUT = "1ターン目の応答"
_TURN2_OUTPUT = "2ターン目の応答"
_COVERED_1 = [{"aspect": "実行単位", "reached_depth": "defined"}]
_T1 = {"response_mode": "deepen", "selected_aspect": "実行単位", "error_summary": ""}
_T2 = {"response_mode": "expand", "selected_aspect": "メモリ空間", "error_summary": ""}

_MESSAGES: list[tuple[str, str]] = [
    ("user", _TOPIC),
    ("assistant", "何を知っていますか？"),
    ("user", "プロセスはプログラムの実行単位です。"),
    ("assistant", _TURN1_OUTPUT),
    ("user", "メモリ空間が独立しています。"),
    ("assistant", _TURN2_OUTPUT),
]


@pytest_asyncio.fixture(loop_scope="session")
async def checkpointer() -> AsyncGenerator[AsyncPostgresSaver]:
    async with AsyncPostgresSaver.from_conn_string(TEST_DATABASE_URL) as saver:
        await saver.setup()
        yield saver


def _state_messages(count: int) -> list[BaseMessage]:
    return [
        AIMessage(content=content) if role == "assistant" else HumanMessage(content=content)
        for role, content in _MESSAGES[:count]
    ]


def _snapshots() -> list[dict[str, Any]]:
    return [
        {"topic": _TOPIC, "turn_count": 1, "messages": _state_messages(2)},
        {"topic": _TOPIC, "turn_count": 1, "messages": _state_messages(3)},
        {
            "topic": _TOPIC,
            "turn_count": 2,
            "messages": _state_messages(4),
            "covered_aspects": _COVERED_1,
            "turn_analysis": _T1,
        },
        {
            "topic": _TOPIC,
            "turn_count": 2,
            "messages": _state_messages(5),
            "covered_aspects": _COVERED_1,
            "turn_analysis": _T1,
        },
        {
            "topic": _TOPIC,
            "turn_count": 3,
            "messages": _state_messages(6),
            "covered_aspects": _COVERED_1,
            "turn_analysis": _T2,
        },
    ]


async def _put_snapshots(saver: AsyncPostgresSaver, session_id: UUID, snapshots: list[dict[str, Any]]) -> None:
    """本番と同じ経路（aput）でスナップショット列を書く。

    リスト・dict の channel は blobs テーブルへ回るため、`channel_versions` と `new_versions` に
    その channel の版を入れないと読み戻しで値が消える（黙って空になる）。
    """
    config: RunnableConfig = {"configurable": {"thread_id": str(session_id), "checkpoint_ns": ""}}
    for step, values in enumerate(snapshots):
        base = empty_checkpoint()
        base["channel_values"] = values
        base["channel_versions"] = {channel: f"{step + 1:032d}.0" for channel in values}
        checkpoint = create_checkpoint(base, None, step)
        config = await saver.aput(config, checkpoint, {"source": "loop", "step": step}, base["channel_versions"])


async def _seed_session(
    conn: asyncpg.Connection,
    user_id: str,
    *,
    session_type: str = "learning",
) -> UUID:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=conn,
        session_id=session_id,
        user_id=user_id,
        session_type=session_type,
        graph_version=GRAPH_VERSION,
    )
    for order, (role, content) in enumerate(_MESSAGES, start=1):
        await dialogue_message_repository.insert(conn, session_id, role, content, order)
    return session_id


async def test_collect_restores_turn_specific_state_from_checkpoints(
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    checkpointer: AsyncPostgresSaver,
) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])
    await _put_snapshots(checkpointer, session_id, _snapshots())
    session = await capture.fetch_session(db_conn, session_id)

    records, warnings = await capture.collect(db_conn, checkpointer, session)

    assert warnings == []
    assert [r["turn"] for r in records] == [4, 6]
    assert [r["dialogue_session_id"] for r in records] == [str(session_id)] * 2
    assert [r["output"] for r in records] == [_TURN1_OUTPUT, _TURN2_OUTPUT]
    assert records[0]["input"]["graph_state"] == {
        "topic": _TOPIC,
        "learning_goal": None,
        "focus_aspects": [],
        "covered_aspects": [],
        "turn_count": 1,
        "turn_analysis": None,
    }
    assert records[1]["input"]["graph_state"]["covered_aspects"] == _COVERED_1
    assert records[1]["input"]["graph_state"]["turn_analysis"] == _T1
    assert records[0]["turn_decision"] == {**_T1, "covered_aspects": _COVERED_1}
    assert records[1]["turn_decision"] == {**_T2, "covered_aspects": _COVERED_1}
    assert len(records[1]["input"]["conversation_history"]) == 5
    assert records[0]["captured_at"].endswith("Z")


async def test_collect_falls_back_when_thread_has_no_checkpoints(
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    checkpointer: AsyncPostgresSaver,
) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])
    session = await capture.fetch_session(db_conn, session_id)

    records, warnings = await capture.collect(db_conn, checkpointer, session)

    assert len(warnings) == 2
    assert set(records[0]["input"]["graph_state"]) == {"topic", "learning_goal", "focus_aspects"}
    assert records[0]["input"]["graph_state"]["topic"] == _TOPIC
    assert "turn_decision" not in records[0]


async def test_collect_rejects_review_session(
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    checkpointer: AsyncPostgresSaver,
) -> None:
    session_id = await _seed_session(db_conn, test_user["id"], session_type="review")
    session = await capture.fetch_session(db_conn, session_id)

    with pytest.raises(ValueError, match="learning"):
        await capture.collect(db_conn, checkpointer, session)


async def test_export_is_idempotent(
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    checkpointer: AsyncPostgresSaver,
    tmp_path: Path,
) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])
    await _put_snapshots(checkpointer, session_id, _snapshots())
    session = await capture.fetch_session(db_conn, session_id)
    out = tmp_path / "generate_questions.jsonl"

    for _ in range(2):
        records, _warnings = await capture.collect(db_conn, checkpointer, session)
        unseen, _skipped = capture.split_unseen(out, records)
        capture.append_records(out, unseen)

    assert len(out.read_text(encoding="utf-8").splitlines()) == 2


async def test_session_lookup_finds_the_latest_learning_session(
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
) -> None:
    await _seed_session(db_conn, test_user["id"], session_type="review")
    session_id = await _seed_session(db_conn, test_user["id"])

    latest = await capture.latest_learning_session(db_conn)
    listed = await capture.list_recent_sessions(db_conn, limit=5)

    assert latest["id"] == session_id
    assert [row["id"] for row in listed] == [session_id]
    assert listed[0]["topic"] == _TOPIC
    assert listed[0]["target_turns"] == 2


async def test_fetch_session_reports_unknown_id(db_conn: asyncpg.Connection) -> None:
    with pytest.raises(LookupError):
        await capture.fetch_session(db_conn, uuid4())


async def test_latest_learning_session_reports_empty_database(db_conn: asyncpg.Connection) -> None:
    with pytest.raises(LookupError):
        await capture.latest_learning_session(db_conn)


async def test_cli_lists_sessions(
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])

    exit_code = await capture.run(capture.parse_args(["--list"]), TEST_DATABASE_URL)

    assert exit_code == 0
    assert str(session_id) in capsys.readouterr().out


async def test_cli_dry_run_does_not_write(
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    checkpointer: AsyncPostgresSaver,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])
    await _put_snapshots(checkpointer, session_id, _snapshots())
    out = tmp_path / "generate_questions.jsonl"

    exit_code = await capture.run(capture.parse_args(["--latest", "--out", str(out), "--dry-run"]), TEST_DATABASE_URL)

    assert exit_code == 0
    assert not out.exists()
    assert _TURN2_OUTPUT in capsys.readouterr().out


async def test_cli_appends_then_skips_on_rerun(
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    checkpointer: AsyncPostgresSaver,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    session_id = await _seed_session(db_conn, test_user["id"])
    await _put_snapshots(checkpointer, session_id, _snapshots())
    out = tmp_path / "generate_questions.jsonl"
    argv = ["--latest", "--out", str(out)]

    first = await capture.run(capture.parse_args(argv), TEST_DATABASE_URL)
    capsys.readouterr()
    second = await capture.run(capture.parse_args(argv), TEST_DATABASE_URL)

    assert (first, second) == (0, 0)
    assert "skipped 2 existing" in capsys.readouterr().out
    assert len(out.read_text(encoding="utf-8").splitlines()) == 2


async def test_cli_reports_review_session_as_error(
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_id = await _seed_session(db_conn, test_user["id"], session_type="review")

    exit_code = await capture.run(capture.parse_args(["--session-id", str(session_id)]), TEST_DATABASE_URL)

    assert exit_code == 1
    assert "learning" in capsys.readouterr().err


async def test_cli_reports_session_without_dialogue_turns(
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    checkpointer: AsyncPostgresSaver,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=db_conn,
        session_id=session_id,
        user_id=test_user["id"],
        session_type="learning",
        graph_version=GRAPH_VERSION,
    )
    for order, (role, content) in enumerate(_MESSAGES[:2], start=1):
        await dialogue_message_repository.insert(db_conn, session_id, role, content, order)

    exit_code = await capture.run(
        capture.parse_args(["--latest", "--out", str(tmp_path / "out.jsonl")]), TEST_DATABASE_URL
    )

    assert exit_code == 1
    assert "対象ターン" in capsys.readouterr().err


async def test_cli_warns_when_checkpoints_are_missing(
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    await _seed_session(db_conn, test_user["id"])
    out = tmp_path / "generate_questions.jsonl"

    exit_code = await capture.run(capture.parse_args(["--latest", "--out", str(out)]), TEST_DATABASE_URL)

    assert exit_code == 0
    assert "warning:" in capsys.readouterr().err
    assert len(out.read_text(encoding="utf-8").splitlines()) == 2


_MAP_MESSAGES: list[tuple[str, str]] = [
    ("user", "TCP について"),
    ("assistant", "聞き取りカード"),
    ("user", "目的: 仕組みの理解"),
    ("assistant", "学習開始の声かけ"),
    ("user", "SYN を送ります"),
    ("assistant", "応答6"),
]
_MAP_ASPECT = {
    "id": "handshake",
    "name": "ハンドシェイク",
    "is_core": True,
    "defined_question": "d",
    "reasoned_question": "r",
    "applied_question": "a",
}
_MAP = {"topic": "TCP の接続確立", "aspects": [_MAP_ASPECT]}
_MAP_DECISION = {
    "response_mode": "deepen",
    "selected_aspect": "ハンドシェイク",
    "selected_aspect_id": "handshake",
    "has_misconception": False,
    "error_summary": "",
    "wrap_up": False,
}


def _map_state_messages(count: int) -> list[BaseMessage]:
    return [
        AIMessage(content=content) if role == "assistant" else HumanMessage(content=content)
        for role, content in _MAP_MESSAGES[:count]
    ]


def _map_snapshots() -> list[dict[str, Any]]:
    base = {"topic": "TCP の接続確立", "intake_complete": True, "intake_message_count": 3}
    return [
        {"topic": "TCP の接続確立", "turn_count": 1, "intake_complete": False, "messages": _map_state_messages(2)},
        {"topic": "TCP の接続確立", "turn_count": 1, "intake_complete": False, "messages": _map_state_messages(3)},
        {
            **base,
            "turn_count": 2,
            "messages": _map_state_messages(4),
            "depth_map": _MAP,
            "map_covered": [],
            "turn_analysis": None,
        },
        {
            **base,
            "turn_count": 2,
            "messages": _map_state_messages(5),
            "depth_map": _MAP,
            "map_covered": [],
            "turn_analysis": None,
        },
        {
            **base,
            "turn_count": 3,
            "messages": _map_state_messages(6),
            "depth_map": _MAP,
            "map_covered": [{"aspect_id": "handshake", "reached_stage": "defined"}],
            "turn_analysis": _MAP_DECISION,
        },
    ]


async def test_collect_captures_a_map_driven_session(
    db_conn: asyncpg.Connection,
    test_user: dict[str, str],
    checkpointer: AsyncPostgresSaver,
) -> None:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=db_conn,
        session_id=session_id,
        user_id=test_user["id"],
        session_type="learning",
        graph_version=GRAPH_VERSION,
    )
    for order, (role, content) in enumerate(_MAP_MESSAGES, start=1):
        await dialogue_message_repository.insert(db_conn, session_id, role, content, order)
    await _put_snapshots(checkpointer, session_id, _map_snapshots())
    session = await capture.fetch_session(db_conn, session_id)

    records, warnings = await capture.collect(db_conn, checkpointer, session)

    assert warnings == []
    assert [r["turn"] for r in records] == [6]
    record = records[0]
    assert record["meta"]["route"] == "map"
    assert record["input"]["graph_state"]["depth_map"] == _MAP
    assert record["input"]["graph_state"]["map_covered"] == []
    assert record["turn_decision"]["map_covered"] == [{"aspect_id": "handshake", "reached_stage": "defined"}]
    assert record["turn_decision"]["selected_aspect_id"] == "handshake"
