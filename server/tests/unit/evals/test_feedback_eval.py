from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from evals import feedback
from evals.feedback import Prediction
from graph.nodes._feedback_assessment import format_conversation_history


def _record(record_id: str, level: str, human: str | None, session_type: str = "learning") -> dict[str, Any]:
    return {
        "id": record_id,
        "session_type": session_type,
        "input": {
            "topic": "プロセス",
            "conversation": [{"role": "human", "content": "プロセス"}, {"role": "ai", "content": "何を？"}],
            "note_text": "トピック: プロセス\n\n本文",
            "aspect_map": None,
        },
        "output": {"understanding_level": level, "strengths": [], "improvements": []},
        "human_level": human,
    }


def _write(path: Path, records: list[dict[str, Any]]) -> Path:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    return path


def _p(level: str, human: str | None, record_id: str = "r", run: int = 0) -> Prediction:
    return Prediction(record_id=record_id, session_type="learning", run=run, level=level, human_level=human)


def test_restored_conversation_formats_like_the_production_state() -> None:
    messages = [HumanMessage(content="プロセス"), AIMessage(content="何を？")]
    conversation = [{"role": m.type, "content": m.content} for m in messages]

    restored = format_conversation_history(feedback.to_messages(conversation))

    assert restored == format_conversation_history(messages)


@pytest.mark.parametrize(
    ("human", "level", "expected"),
    [("low", "medium", "lenient"), ("high", "medium", "strict"), ("medium", "medium", "agree")],
)
def test_direction_compares_the_rank(human: str, level: str, expected: str) -> None:
    assert feedback.direction(human, level) == expected


def test_agreement_counts_only_labeled_predictions() -> None:
    result = feedback.agreement(
        [_p("medium", "low"), _p("low", "low"), _p("medium", "medium"), _p("medium", "high"), _p("high", None)]
    )

    assert result["labeled"] == 4
    assert result["exact"]["count"] == 2
    assert result["lenient"]["count"] == 1
    assert result["strict"]["count"] == 1
    assert result["low_overrated"] == {**result["low_overrated"], "count": 1, "total": 2, "rate": 0.5}
    assert result["confusion"]["low"] == {"low": 1, "medium": 1, "high": 0}


def test_agreement_without_labels_has_no_rate() -> None:
    result = feedback.agreement([_p("medium", None)])

    assert result["exact"] == {"count": 0, "total": 0, "rate": None, "ci95": None}


def test_stability_lists_records_whose_runs_disagree() -> None:
    result = feedback.stability(
        [
            _p("medium", None, "a", 0),
            _p("medium", None, "a", 1),
            _p("high", None, "b", 0),
            _p("medium", None, "b", 1),
            _p("low", None, "c", 0),
        ]
    )

    assert result["records"] == 2
    assert result["unanimous"]["count"] == 1
    assert result["unstable"] == {"b": {"medium": 1, "high": 1}}
    assert result["mean_modal_share"] == 0.75


async def test_scoring_reads_the_stored_level_without_calling_the_llm(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "f.jsonl", [_record("a", "medium", "low"), _record("b", "low", "low")])
    out = tmp_path / "report.json"

    async def _fail(record: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("scoring must not assess")

    code = await feedback.run(feedback.parse_args(["--dataset", str(dataset), "--out", str(out)]), _fail)

    report = json.loads(out.read_text(encoding="utf-8"))
    assert code == 0
    assert report["agreement"]["low_overrated"]["count"] == 1
    assert report["meta"]["labeled_records"] == 2


async def test_regression_resumes_from_the_checkpoint(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "f.jsonl", [_record("a", "medium", "low")])
    calls: list[str] = []

    async def _assessor(record: dict[str, Any]) -> dict[str, Any]:
        calls.append(record["id"])
        return {"understanding_level": "low"}

    argv = [
        "--mode",
        "regression",
        "--runs",
        "2",
        "--dataset",
        str(dataset),
        "--checkpoint-dir",
        str(tmp_path / "ckpt"),
        "--out",
        str(tmp_path / "report.json"),
    ]
    assert await feedback.run(feedback.parse_args(argv), _assessor) == 0
    assert await feedback.run(feedback.parse_args(argv), _assessor) == 0

    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert calls == ["a", "a"]
    assert report["agreement"]["exact"]["count"] == 2
    assert report["stability"]["unanimous"]["count"] == 1


async def test_regression_reassesses_when_the_input_changed(tmp_path: Path) -> None:
    record = _record("a", "medium", None)
    dataset = _write(tmp_path / "f.jsonl", [record])
    calls: list[str] = []

    async def _assessor(record: dict[str, Any]) -> dict[str, Any]:
        calls.append(record["input"]["note_text"])
        return {"understanding_level": "medium"}

    argv = ["--mode", "regression", "--runs", "1", "--dataset", str(dataset)]
    argv += ["--checkpoint-dir", str(tmp_path / "ckpt"), "--out", str(tmp_path / "r.json")]
    await feedback.run(feedback.parse_args(argv), _assessor)
    record["input"]["note_text"] = "変えた"
    _write(dataset, [record])
    await feedback.run(feedback.parse_args(argv), _assessor)

    assert calls == ["トピック: プロセス\n\n本文", "変えた"]


async def test_regression_records_a_failed_run_and_exits_nonzero(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "f.jsonl", [_record("a", "medium", "low")])

    async def _assessor(record: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("broken")

    argv = ["--mode", "regression", "--runs", "1", "--dataset", str(dataset)]
    argv += ["--checkpoint-dir", str(tmp_path / "ckpt"), "--out", str(tmp_path / "r.json")]

    assert await feedback.run(feedback.parse_args(argv), _assessor) == 1
    report = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert report["errors"] == ["a run0: ValueError: broken"]


async def test_trace_rejects_an_unknown_id(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "f.jsonl", [_record("a", "medium", None)])

    assert await feedback.run(feedback.parse_args(["--dataset", str(dataset), "--trace", "nope"])) == 1


async def test_list_unannotated(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    dataset = _write(tmp_path / "f.jsonl", [_record("a", "medium", None), _record("b", "low", "low")])

    await feedback.run(feedback.parse_args(["--dataset", str(dataset), "--list-unannotated"]))

    assert capsys.readouterr().out.split() == ["a"]
