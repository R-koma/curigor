"""capture の純関数（ターン選別・スナップショット対応付け・レコード組み立て）の検査。

DB とチェックポイントに触る経路は tests/integration/test_capture.py が受け持つ。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from evals.tools import capture
from graph.llm import llm
from graph.prompts.question import PROMPT_FINGERPRINT, PROMPT_VERSION

SESSION_ID = UUID("a1b2c3d4-0000-4000-8000-000000000001")
STARTED_AT = datetime(2026, 9, 9, 1, 0, tzinfo=UTC)


def _message(order: int, role: str, content: str, minute: int = 0) -> dict[str, Any]:
    return {
        "role": role,
        "content": content,
        "message_order": order,
        "created_at": datetime(2026, 9, 9, 1, minute, tzinfo=UTC),
    }


def _messages() -> list[dict[str, Any]]:
    return [
        _message(1, "user", "プロセス"),
        _message(2, "assistant", "何を知っていますか？", minute=1),
        _message(3, "user", "プロセスはプログラムの実行単位です。", minute=2),
        _message(4, "assistant", "1ターン目の応答", minute=3),
        _message(5, "user", "メモリ空間が独立しています。", minute=4),
        _message(6, "assistant", "2ターン目の応答", minute=5),
    ]


def _snapshot(
    contents: list[tuple[str, str]],
    *,
    turn_count: int,
    covered: list[dict[str, str]] | None = None,
    turn_analysis: dict[str, str] | None = None,
    with_turn_analysis_key: bool = True,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "topic": "プロセス",
        "turn_count": turn_count,
        "messages": [
            AIMessage(content=text) if role == "ai" else HumanMessage(content=text) for role, text in contents
        ],
    }
    if covered is not None:
        values["covered_aspects"] = covered
    if with_turn_analysis_key:
        values["turn_analysis"] = turn_analysis
    return values


_COVERED_1 = [{"aspect": "実行単位", "reached_depth": "defined"}]
_COVERED_2 = [*_COVERED_1, {"aspect": "メモリ空間", "reached_depth": "defined"}]
_T1 = {"response_mode": "deepen", "selected_aspect": "実行単位", "error_summary": ""}
_T2 = {"response_mode": "expand", "selected_aspect": "メモリ空間", "error_summary": ""}


def _snapshots() -> list[dict[str, Any]]:
    """本番のターン進行（interrupt → 応答 → 次ターン）に対応するスナップショット列。"""
    start = [("human", "プロセス"), ("ai", "何を知っていますか？")]
    turn1_input = [*start, ("human", "プロセスはプログラムの実行単位です。")]
    turn1_done = [*turn1_input, ("ai", "1ターン目の応答")]
    turn2_input = [*turn1_done, ("human", "メモリ空間が独立しています。")]
    turn2_done = [*turn2_input, ("ai", "2ターン目の応答")]
    return [
        _snapshot(start, turn_count=1),
        _snapshot(turn1_input, turn_count=1),
        _snapshot(turn1_done, turn_count=2, covered=_COVERED_1, turn_analysis=_T1),
        _snapshot(turn2_input, turn_count=2, covered=_COVERED_1, turn_analysis=_T1),
        _snapshot(turn2_done, turn_count=3, covered=_COVERED_2, turn_analysis=_T2),
    ]


def test_target_turns_excludes_learning_start_response() -> None:
    orders = [m["message_order"] for m in capture.target_turns(_messages())]
    assert orders == [4, 6]


def test_target_turns_empty_when_no_dialogue_response() -> None:
    assert capture.target_turns(_messages()[:3]) == []


def test_conversation_history_includes_topic_and_start_response() -> None:
    history = capture.conversation_history(_messages(), 4)
    assert history == [
        {"role": "user", "content": "プロセス"},
        {"role": "assistant", "content": "何を知っていますか？"},
        {"role": "user", "content": "プロセスはプログラムの実行単位です。"},
    ]


def test_find_turn_snapshots_separates_input_from_decision() -> None:
    snapshots = _snapshots()

    turn1 = capture.find_turn_snapshots(snapshots, 3, "1ターン目の応答")
    turn2 = capture.find_turn_snapshots(snapshots, 5, "2ターン目の応答")

    assert turn1 is not None and turn2 is not None
    assert turn1.pre["turn_analysis"] is None
    assert "covered_aspects" not in turn1.pre
    assert turn1.post["turn_analysis"] == _T1
    assert turn2.pre["turn_analysis"] == _T1
    assert turn2.pre["turn_count"] == 2
    assert turn2.post["turn_analysis"] == _T2


def test_find_turn_snapshots_returns_none_when_output_is_absent() -> None:
    assert capture.find_turn_snapshots(_snapshots(), 3, "撮り直した別の応答") is None


def test_find_turn_snapshots_skips_cancelled_turn() -> None:
    """取り消されたターンと同じメッセージ件数が再度現れても、生き残った側の直前を採る。"""
    start = [("human", "プロセス"), ("ai", "何を知っていますか？")]
    turn_input = [*start, ("human", "プロセスはプログラムの実行単位です。")]
    snapshots = [
        _snapshot(turn_input, turn_count=1, turn_analysis=None),
        _snapshot([*turn_input, ("ai", "取り消された応答")], turn_count=2, turn_analysis=_T1),
        _snapshot(start, turn_count=1, turn_analysis=_T1),
        _snapshot(turn_input, turn_count=1, turn_analysis=_T2),
        _snapshot([*turn_input, ("ai", "やり直した応答")], turn_count=2, turn_analysis=_T1),
    ]

    turn = capture.find_turn_snapshots(snapshots, 3, "やり直した応答")

    assert turn is not None
    assert turn.pre["turn_analysis"] == _T2


def test_to_graph_state_writes_null_for_turn_without_analysis() -> None:
    values = _snapshot([("human", "プロセス")], turn_count=1, turn_analysis=None)

    graph_state = capture.to_graph_state(values)

    assert graph_state["turn_analysis"] is None
    assert graph_state["covered_aspects"] == []
    assert graph_state["learning_goal"] is None
    assert graph_state["focus_aspects"] == []


def test_to_graph_state_tolerates_checkpoint_without_turn_analysis_key() -> None:
    values = _snapshot([("human", "プロセス")], turn_count=1, with_turn_analysis_key=False)

    assert "turn_analysis" not in values
    assert capture.to_graph_state(values)["turn_analysis"] is None


def test_to_graph_state_carries_wrap_up_offered() -> None:
    values = _snapshot([("human", "プロセス")], turn_count=1)
    values["wrap_up_offered"] = True

    assert capture.to_graph_state(values)["wrap_up_offered"] is True


def test_to_graph_state_omits_wrap_up_offered_for_checkpoints_before_the_feature() -> None:
    values = _snapshot([("human", "プロセス")], turn_count=1)

    assert "wrap_up_offered" not in capture.to_graph_state(values)


def test_build_records_carries_turn_specific_state() -> None:
    records, warnings = capture.build_records(SESSION_ID, STARTED_AT, _messages(), _snapshots())

    assert warnings == []
    assert [r["id"] for r in records] == ["2026-09-09-a1b2c3d4__t4", "2026-09-09-a1b2c3d4__t6"]
    assert [r["turn"] for r in records] == [4, 6]
    assert records[0]["input"]["graph_state"]["turn_analysis"] is None
    assert records[0]["input"]["graph_state"]["turn_count"] == 1
    assert records[1]["input"]["graph_state"]["turn_analysis"] == _T1
    assert records[1]["input"]["graph_state"]["covered_aspects"] == _COVERED_1
    assert records[0]["turn_decision"] == {**_T1, "covered_aspects": _COVERED_1}
    assert records[1]["turn_decision"] == {**_T2, "covered_aspects": _COVERED_2}
    assert records[1]["output"] == "2ターン目の応答"
    assert records[1]["captured_at"] == "2026-09-09T01:05:00Z"
    assert [r["note"] for r in records] == ["", ""]


def test_build_records_omits_turn_specific_keys_when_snapshot_unmatched() -> None:
    records, warnings = capture.build_records(SESSION_ID, STARTED_AT, _messages(), [])

    assert len(warnings) == 2
    graph_state = records[0]["input"]["graph_state"]
    assert set(graph_state) == {"topic", "learning_goal", "focus_aspects"}
    assert "turn_decision" not in records[0]
    assert graph_state["topic"] == "プロセス"
    assert records[0]["note"].startswith("capture:")


def test_build_record_meta_comes_from_code_constants() -> None:
    records, _ = capture.build_records(SESSION_ID, STARTED_AT, _messages(), _snapshots())

    assert records[0]["meta"] == {
        "model": llm.model_name,
        "prompt_version": PROMPT_VERSION,
        "prompt_fingerprint": PROMPT_FINGERPRINT,
        "params": {"temperature": llm.temperature},
        "captured_by": capture.CAPTURED_BY,
    }


def test_build_record_key_order_extends_the_existing_dataset_shape() -> None:
    """既存レコードのキー順を保ったまま、`turn_decision` だけを `output` の直後に足す。"""
    dataset = Path(__file__).resolve().parents[3] / "evals" / "datasets" / "generate_questions.jsonl"
    with dataset.open(encoding="utf-8") as f:
        existing = json.loads(next(line for line in f if line.strip()))
    records, _ = capture.build_records(SESSION_ID, STARTED_AT, _messages(), _snapshots())
    keys = list(records[0])

    assert [k for k in keys if k != "turn_decision"] == list(existing)
    assert keys.index("turn_decision") == keys.index("output") + 1
    assert records[0]["schema_version"] == existing["schema_version"]
    assert list(records[0]["meta"]) == [
        "model",
        "prompt_version",
        "prompt_fingerprint",
        "params",
        "captured_by",
    ]


def test_session_label_uses_user_timezone_for_the_calendar_day() -> None:
    late_night_jst = datetime(2026, 9, 8, 15, 30, tzinfo=UTC)

    assert capture.session_label(SESSION_ID, late_night_jst) == "2026-09-09-a1b2c3d4"


def test_split_unseen_skips_ids_already_in_the_dataset(tmp_path: Path) -> None:
    out = tmp_path / "generate_questions.jsonl"
    records, _ = capture.build_records(SESSION_ID, STARTED_AT, _messages(), _snapshots())

    unseen, skipped = capture.split_unseen(out, records)
    capture.append_records(out, unseen)
    again, skipped_again = capture.split_unseen(out, records)

    assert (len(unseen), skipped) == (2, 0)
    assert (again, skipped_again) == ([], 2)
    assert len(out.read_text(encoding="utf-8").splitlines()) == 2


def test_append_records_writes_unescaped_json_lines(tmp_path: Path) -> None:
    out = tmp_path / "out.jsonl"
    records, _ = capture.build_records(SESSION_ID, STARTED_AT, _messages(), _snapshots())

    capture.append_records(out, records)

    lines = out.read_text(encoding="utf-8").splitlines()
    assert "プロセス" in lines[0]
    assert [json.loads(line)["id"] for line in lines] == [r["id"] for r in records]


def test_find_turn_snapshots_matches_ai_message_with_content_blocks() -> None:
    """応答が文字列ではなくブロック列で返るモデルでも本文一致で対応付けできる。"""
    snapshots = [
        _snapshot([("human", "プロセス")], turn_count=1, turn_analysis=_T1),
        {
            "topic": "プロセス",
            "turn_count": 2,
            "messages": [
                HumanMessage(content="プロセス"),
                AIMessage(content=[{"type": "text", "text": "1ターン"}, {"type": "text", "text": "目の応答"}]),
            ],
            "turn_analysis": _T2,
        },
    ]

    turn = capture.find_turn_snapshots(snapshots, 1, "1ターン目の応答")

    assert turn is not None
    assert turn.pre["turn_analysis"] == _T1


def test_print_sessions_tolerates_session_without_messages(capsys: pytest.CaptureFixture[str]) -> None:
    sessions = [{"id": SESSION_ID, "status": "abandoned", "started_at": STARTED_AT, "topic": None, "target_turns": 0}]

    capture.print_sessions(sessions, captured=set())

    assert str(SESSION_ID) in capsys.readouterr().out


def test_turn_decision_is_null_when_no_analysis_ran() -> None:
    """分析が走らなかったターンはプロンプトの coverage も merge 前と同じなので null で足りる。"""
    post = _snapshot([("human", "プロセス")], turn_count=2, covered=_COVERED_1, turn_analysis=None)

    assert capture.turn_decision_field(post) == {"turn_decision": None}


def test_turn_decision_is_omitted_for_checkpoints_without_the_field() -> None:
    post = _snapshot([("human", "プロセス")], turn_count=2, with_turn_analysis_key=False)

    assert capture.turn_decision_field(post) == {}


def test_target_turns_skips_a_turn_whose_user_message_has_images() -> None:
    """画像を jsonl に載せない方針なので、画像付きターンはレコード化しない。"""
    image_message_id = UUID("00000000-0000-4000-8000-00000000000f")
    messages = _messages()
    messages[4]["id"] = image_message_id

    orders = [m["message_order"] for m in capture.target_turns(messages, {image_message_id})]

    assert orders == [4]


def test_build_records_warns_about_skipped_image_turn() -> None:
    image_message_id = UUID("00000000-0000-4000-8000-00000000000f")
    messages = _messages()
    messages[4]["id"] = image_message_id

    records, warnings = capture.build_records(SESSION_ID, STARTED_AT, messages, _snapshots(), {image_message_id})

    assert [r["turn"] for r in records] == [4]
    assert any("画像" in w for w in warnings)


def test_captured_session_ids_reads_the_dataset(tmp_path: Path) -> None:
    out = tmp_path / "out.jsonl"
    records, _ = capture.build_records(SESSION_ID, STARTED_AT, _messages(), _snapshots())
    capture.append_records(out, records)

    assert capture.captured_session_ids(out) == {str(SESSION_ID)}
    assert capture.captured_session_ids(tmp_path / "missing.jsonl") == set()


def test_duplicate_user_message_is_reported() -> None:
    messages = _messages()
    messages.insert(3, _message(4, "user", messages[2]["content"]))
    for order, message in enumerate(messages, start=1):
        message["message_order"] = order

    _records, warnings = capture.build_records(SESSION_ID, STARTED_AT, messages, [])

    assert any("再送の可能性" in w for w in warnings)
