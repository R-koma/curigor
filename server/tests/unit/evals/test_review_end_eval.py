from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from evals import review_end
from evals.review_end import Prediction
from graph.nodes._shared import recent_messages_block
from graph.output_schemas import ReviewTurnAnalysis

_END_CATEGORIES = frozenset({"end", "update_note", "answer_with_end"})
_CONTINUE_CATEGORIES = frozenset({"exhausted", "dont_know", "answer", "question", "move_on"})


def _record(rid: str, expected: bool, utterance: str = "以上です", category: str = "exhausted") -> dict[str, Any]:
    return {
        "id": rid,
        "category": category,
        "topic": "二分探索",
        "conversation": [
            {"role": "human", "content": "二分探索"},
            {"role": "ai", "content": "説明してみてください。"},
            {"role": "human", "content": utterance},
        ],
        "expected": expected,
    }


def _p(predicted: bool, expected: bool, record_id: str = "r", run: int = 0) -> Prediction:
    return Prediction(record_id=record_id, category="c", run=run, predicted=predicted, expected=expected)


def _write(path: Path, records: list[dict[str, Any]]) -> Path:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    return path


def test_state_renders_the_conversation_like_the_review_session() -> None:
    state = review_end.to_state(_record("r", False))

    assert state["topic"] == "二分探索"
    assert recent_messages_block(state) == "ユーザー: 二分探索\nAI: 説明してみてください。\nユーザー: 以上です"


def test_agreement_separates_false_and_missed_ends() -> None:
    result = review_end.agreement([_p(True, False), _p(False, False), _p(False, True), _p(True, True), _p(True, True)])

    assert result["accuracy"]["count"] == 3
    assert result["false_end"] == {**result["false_end"], "count": 1, "total": 2}
    assert result["missed_end"] == {**result["missed_end"], "count": 1, "total": 3}


def test_stability_lists_records_whose_runs_disagree() -> None:
    result = review_end.stability(
        [_p(True, True, "a", 0), _p(True, True, "a", 1), _p(True, False, "b", 0), _p(False, False, "b", 1)]
    )

    assert result["records"] == 2
    assert result["unanimous"]["count"] == 1
    assert result["unstable"] == {"b": {"true": 1, "false": 1}}


async def test_classify_retries_a_failed_analysis() -> None:
    analyze = AsyncMock(side_effect=[None, ReviewTurnAnalysis(wants_to_end_session=True)])
    with (
        patch("evals.review_end.analyze_review_turn", analyze),
        patch("evals.review_end._RETRY_BASE_DELAY_SECONDS", 0),
    ):
        assert await review_end.classify(_record("r", True)) is True
    assert analyze.await_count == 2


async def test_classify_gives_up_after_repeated_failures() -> None:
    with (
        patch("evals.review_end.analyze_review_turn", AsyncMock(return_value=None)),
        patch("evals.review_end._RETRY_BASE_DELAY_SECONDS", 0),
        pytest.raises(review_end.AnalysisFailed),
    ):
        await review_end.classify(_record("r", True))


async def test_run_writes_the_report_and_resumes_from_the_checkpoint(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "data.jsonl", [_record("keep", False), _record("end", True, "今日はここまで", "end")])
    calls: list[str] = []

    async def classifier(record: dict[str, Any]) -> bool:
        calls.append(record["id"])
        return True

    argv = ["--runs", "2", "--dataset", str(dataset), "--checkpoint-dir", str(tmp_path / "ckpt")]
    out = tmp_path / "report.json"
    assert await review_end.run(review_end.parse_args([*argv, "--out", str(out)]), classifier) == 0
    assert await review_end.run(review_end.parse_args([*argv, "--out", str(out)]), classifier) == 0

    assert Counter(calls) == {"keep": 2, "end": 2}
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["agreement"]["false_end"]["count"] == 2
    assert report["misjudged"] == ["keep"]
    assert report["by_category"]["end"]["accuracy"]["rate"] == 1.0


async def test_run_stops_when_the_analysis_keeps_failing(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "data.jsonl", [_record("r", False)])

    async def classifier(record: dict[str, Any]) -> bool:
        raise review_end.AnalysisFailed("failed")

    args = review_end.parse_args(["--dataset", str(dataset), "--checkpoint-dir", str(tmp_path / "ckpt")])
    assert await review_end.run(args, classifier) == 1


async def test_run_rejects_unknown_trace(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "data.jsonl", [_record("r", False)])

    args = review_end.parse_args(["--dataset", str(dataset), "--trace", "missing"])
    assert await review_end.run(args, AsyncMock()) == 1


def test_dataset_ids_are_unique() -> None:
    counts = Counter(record["id"] for record in review_end.load_records())
    assert [record_id for record_id, count in counts.items() if count > 1] == []


def test_dataset_expectations_follow_the_category() -> None:
    problems = [
        f"{record['id']}: {record['category']} expected={record['expected']}"
        for record in review_end.load_records()
        if record["expected"] is not (record["category"] in _END_CATEGORIES)
        or record["category"] not in _END_CATEGORIES | _CONTINUE_CATEGORIES
    ]
    assert problems == []


def test_dataset_conversations_start_like_a_review_session() -> None:
    problems = [
        record["id"]
        for record in review_end.load_records()
        if record["conversation"][0] != {"role": "human", "content": record["topic"]}
        or record["conversation"][-1]["role"] != "human"
    ]
    assert problems == []


def test_dataset_covers_the_answers_that_ran_out() -> None:
    utterances = {r["conversation"][-1]["content"] for r in review_end.load_records() if r["category"] == "exhausted"}
    assert {"以上です", "他は思い出せません"} <= utterances
