from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from evals import feedback
from evals.checkpoint import sha256_bytes
from evals.feedback import Prediction
from evals.llm_usage import current_recorder
from evals.model_override import FEEDBACK_EVAL_TASKS, models_meta
from graph.llm import RESPONSE_MODELS, STRUCTURED_MODELS
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


@pytest.fixture
def restore_models() -> Iterator[None]:
    response, structured = dict(RESPONSE_MODELS), dict(STRUCTURED_MODELS)
    yield
    RESPONSE_MODELS.clear()
    RESPONSE_MODELS.update(response)
    STRUCTURED_MODELS.clear()
    STRUCTURED_MODELS.update(structured)


def _usage_call(task: str = "analyze-dialogue") -> dict[str, Any]:
    return {
        "task": task,
        "model": "gpt-6-luna",
        "input_tokens": 10,
        "cached_input_tokens": 0,
        "output_tokens": 5,
        "reasoning_tokens": 0,
        "seconds": 1.0,
    }


async def _recording_assessor(record: dict[str, Any]) -> dict[str, Any]:
    recorder = current_recorder()
    assert recorder is not None
    recorder.calls.append(_usage_call())
    return {"understanding_level": "low"}


def _regression_argv(tmp_path: Path, dataset: Path, *extra: str) -> list[str]:
    return [
        "--mode",
        "regression",
        "--runs",
        "1",
        "--dataset",
        str(dataset),
        "--checkpoint-dir",
        str(tmp_path / "ckpt"),
        "--out",
        str(tmp_path / "report.json"),
        *extra,
    ]


async def test_regression_reports_usage_and_models(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "f.jsonl", [_record("a", "medium", "low")])

    code = await feedback.run(feedback.parse_args(_regression_argv(tmp_path, dataset)), _recording_assessor)

    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert code == 0
    assert report["usage"]["tasks"]["analyze-dialogue"]["calls"] == 1
    assert report["meta"]["models"] == models_meta(FEEDBACK_EVAL_TASKS)
    assert report["meta"]["dataset_sha256"] == sha256_bytes(dataset.read_bytes())


async def test_resume_keeps_saved_usage(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "f.jsonl", [_record("a", "medium", "low")])
    argv = _regression_argv(tmp_path, dataset)
    await feedback.run(feedback.parse_args(argv), _recording_assessor)

    async def _must_not_run(record: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("保存済みの run を作り直してはいけない")

    assert await feedback.run(feedback.parse_args(argv), _must_not_run) == 0

    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["usage"]["tasks"]["analyze-dialogue"]["calls"] == 1


async def test_scoring_report_has_no_usage(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "f.jsonl", [_record("a", "medium", "low")])
    out = tmp_path / "report.json"

    await feedback.run(feedback.parse_args(["--dataset", str(dataset), "--out", str(out)]))

    assert "usage" not in json.loads(out.read_text(encoding="utf-8"))


@pytest.mark.parametrize("extra", [["--mode", "scoring"], ["--list-unannotated"]])
async def test_model_is_rejected_without_generation(tmp_path: Path, extra: list[str], restore_models: None) -> None:
    dataset = _write(tmp_path / "f.jsonl", [_record("a", "medium", "low")])
    before = (dict(RESPONSE_MODELS), dict(STRUCTURED_MODELS))
    argv = ["--dataset", str(dataset), "--model", "analyze-dialogue=openai:gpt-x", *extra]

    assert await feedback.run(feedback.parse_args(argv)) == 1

    assert (dict(RESPONSE_MODELS), dict(STRUCTURED_MODELS)) == before


async def test_rejects_task_it_does_not_call(tmp_path: Path, restore_models: None) -> None:
    dataset = _write(tmp_path / "f.jsonl", [_record("a", "medium", "low")])
    argv = _regression_argv(tmp_path, dataset, "--model", "learning-dialogue=openai:gpt-x")

    assert await feedback.run(feedback.parse_args(argv), _recording_assessor) == 1


async def test_override_changes_the_report_and_the_manifest(tmp_path: Path, restore_models: None) -> None:
    dataset = _write(tmp_path / "f.jsonl", [_record("a", "medium", "low")])
    argv = _regression_argv(tmp_path, dataset, "--model", "analyze-dialogue=openai:gpt-x")

    assert await feedback.run(feedback.parse_args(argv), _recording_assessor) == 0

    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["meta"]["models"]["analyze-dialogue"]["model"] == "gpt-x"
    manifest = json.loads((tmp_path / "ckpt" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["models"]["analyze-dialogue"]["model"] == "gpt-x"


async def test_override_never_called_returns_1_after_writing_the_report(tmp_path: Path, restore_models: None) -> None:
    dataset = _write(tmp_path / "f.jsonl", [_record("a", "medium", "low")])
    argv = _regression_argv(tmp_path, dataset, "--model", "generate-feedback-scores=openai:gpt-x")

    assert await feedback.run(feedback.parse_args(argv), _recording_assessor) == 1

    assert (tmp_path / "report.json").exists()
