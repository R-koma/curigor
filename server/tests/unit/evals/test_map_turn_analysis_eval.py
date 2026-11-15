from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from evals import map_turn_analysis as eval_module
from evals.checkpoint import sha256_bytes
from evals.dataset import SourceTrace
from evals.llm_usage import current_recorder
from evals.map_turn_analysis import Prediction
from evals.map_turn_analysis_dataset import USER_INTENTS
from evals.metrics import format_rate
from evals.model_override import MAP_TURN_ANALYSIS_TASKS, models_meta
from evals.review_end import AnalysisFailed
from graph.llm import RESPONSE_MODELS, STRUCTURED_MODELS
from graph.output_schemas import MapDialogueTurnAnalysis
from graph.prompts.map_turn_analysis import MAP_TURN_ANALYSIS_PROMPT_FINGERPRINT

_OK = {"has_misconception": False, "user_intent": "explanation"}


def _source(record_id: str, last: str = "スタックは後入れ先出しです。", **meta: Any) -> dict[str, Any]:
    return {
        "id": record_id,
        "turn": 2,
        "meta": {"route": "map", "captured_by": "capture", **meta},
        "input": {
            "conversation_history": [
                {"role": "assistant", "content": "説明してみてください。"},
                {"role": "user", "content": last},
            ],
            "graph_state": {
                "topic": "スタック",
                "depth_map": {"aspects": [{"id": "a1", "name": "LIFO", "is_core": True}]},
                "map_covered": [],
                "intake_message_count": 0,
                "wrap_up_offered": False,
            },
        },
        "output": "応答",
    }


def _expected(misconception: bool | None, intent: str | None) -> dict[str, Any]:
    return {"has_misconception": misconception, "user_intent": intent}


def _row(
    row_id: str,
    expected: dict[str, Any] | None,
    *,
    source: str = "real",
    unclear: list[str] | None = None,
    last: str | None = None,
    category: str | None = None,
    base: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": row_id,
        "source": source,
        "base": base or row_id,
        "expected": expected,
        "unclear": unclear or [],
        "note": "",
        "annotated_at": None,
    }
    if source == "handwritten":
        row["last_user_message"] = last or "手書きの発言"
        row["category"] = category or "misconception"
    return row


def _p(
    predicted: tuple[bool, str],
    expected: tuple[bool | None, str | None],
    *,
    record_id: str = "r",
    source: str = "real",
    run: int = 0,
    unclear: tuple[str, ...] = (),
    category: str | None = None,
) -> Prediction:
    return Prediction(
        record_id=record_id,
        source=source,
        category=category,
        run=run,
        predicted={"has_misconception": predicted[0], "user_intent": predicted[1]},
        expected=_expected(*expected),
        unclear=unclear,
    )


def _write(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return path


def _argv(tmp_path: Path, dataset: Path, *extra: str, checkpoint: str = "ckpt") -> list[str]:
    return [
        "--runs",
        "1",
        "--dataset",
        str(dataset),
        "--checkpoint-dir",
        str(tmp_path / checkpoint),
        "--out",
        str(tmp_path / "report.json"),
        *extra,
    ]


def _report(tmp_path: Path) -> dict[str, Any]:
    report: dict[str, Any] = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    return report


async def _always_ok(trace: SourceTrace) -> dict[str, Any]:
    return dict(_OK)


def _analysis(**overrides: Any) -> MapDialogueTurnAnalysis:
    fields: dict[str, Any] = {
        "user_intent": "explanation",
        "has_misconception": False,
        "response_mode": "deepen",
        "selected_aspect_id": "a1",
    }
    return MapDialogueTurnAnalysis(**(fields | overrides))


def _by_message(decisions: dict[str, dict[str, Any]]) -> Any:
    async def classifier(trace: SourceTrace) -> dict[str, Any]:
        return decisions.get(trace.input["conversation_history"][-1]["content"], dict(_OK))

    return classifier


def _runs(
    record_id: str, decisions: list[tuple[bool, str]], expected: tuple[bool | None, str | None], **kw: Any
) -> list[Prediction]:
    return [_p(decision, expected, record_id=record_id, run=i, **kw) for i, decision in enumerate(decisions)]


def test_misconception_metrics_separates_missed_and_false_alarm() -> None:
    predictions = [
        _p((True, "explanation"), (False, "explanation"), record_id="a"),
        _p((False, "explanation"), (False, "explanation"), record_id="b"),
        _p((False, "explanation"), (True, "explanation"), record_id="c"),
        _p((True, "explanation"), (True, "explanation"), record_id="d"),
        _p((True, "explanation"), (True, "explanation"), record_id="e"),
    ]

    result = eval_module.misconception_metrics(predictions)

    assert result["total"] == 5
    assert result["accuracy"]["count"] == 3
    assert (result["missed"]["count"], result["missed"]["total"]) == (1, 3)
    assert (result["false_alarm"]["count"], result["false_alarm"]["total"]) == (1, 2)


def test_rates_count_each_record_once_so_more_runs_do_not_narrow_the_interval() -> None:
    def metrics(runs: int) -> dict[str, Any]:
        predictions: list[Prediction] = []
        for i in range(10):
            detected = i >= 5
            predictions += _runs(f"r{i}", [(detected, "explanation")] * runs, (True, "explanation"))
        return eval_module.misconception_metrics(predictions)

    one, three = metrics(1), metrics(3)

    assert one["missed"] == three["missed"]
    assert (three["missed"]["count"], three["missed"]["total"]) == (5, 10)
    assert three["total"] == 10


def test_a_record_is_classified_by_the_majority_of_its_runs_and_a_tie_is_wrong() -> None:
    expected = (True, "explanation")
    predictions = [
        *_runs("two_of_three", [(True, "explanation"), (True, "explanation"), (False, "explanation")], expected),
        *_runs("tie", [(True, "explanation"), (False, "explanation")], expected),
        *_runs("one_of_three", [(True, "explanation"), (False, "explanation"), (False, "explanation")], expected),
    ]

    result = eval_module.misconception_metrics(predictions)

    assert (result["missed"]["count"], result["missed"]["total"]) == (2, 3)
    assert result["accuracy"]["count"] == 1


def test_false_alarm_also_counts_per_record_by_majority() -> None:
    expected = (False, "explanation")
    predictions = [
        *_runs("flagged", [(True, "explanation"), (True, "explanation"), (False, "explanation")], expected),
        *_runs("tie", [(True, "explanation"), (False, "explanation")], expected),
        *_runs("clean", [(False, "explanation")] * 3, expected),
    ]

    result = eval_module.misconception_metrics(predictions)

    assert (result["false_alarm"]["count"], result["false_alarm"]["total"]) == (2, 3)


def test_misconception_metrics_has_no_rate_when_a_side_is_absent() -> None:
    result = eval_module.misconception_metrics([_p((False, "explanation"), (False, "explanation"))])

    assert result["missed"]["total"] == 0
    assert result["missed"]["rate"] is None
    assert format_rate(result["missed"]) == "-（0 件）"


def test_intent_metrics_reports_every_class_and_the_confusion() -> None:
    predictions = [
        _p((False, "question"), (False, "question"), record_id="a"),
        _p((False, "explanation"), (False, "question"), record_id="b"),
        _p((False, "end_session"), (False, "exhausted"), record_id="c"),
        _p((False, "exhausted"), (False, "exhausted"), record_id="d"),
        _p((False, "exhausted"), (False, "exhausted"), record_id="e"),
    ]

    result = eval_module.intent_metrics(predictions)

    assert result["total"] == 5
    assert result["accuracy"]["count"] == 3
    assert set(result["by_class"]) == set(USER_INTENTS)
    assert result["by_class"]["question"]["count"] == 1
    assert result["by_class"]["exhausted"]["total"] == 3
    assert result["by_class"]["dont_know"]["rate"] is None
    assert result["confusion"] == {
        "question": {"question": 1, "explanation": 1},
        "exhausted": {"end_session": 1, "exhausted": 2},
    }


def test_intent_confusion_uses_the_majority_label_per_record() -> None:
    expected = (False, "question")
    predictions = [
        *_runs("m", [(False, "question"), (False, "explanation"), (False, "explanation")], expected),
        *_runs("t", [(False, "question"), (False, "explanation")], expected),
    ]

    result = eval_module.intent_metrics(predictions)

    assert result["total"] == 2
    assert result["confusion"] == {"question": {"explanation": 2}}
    assert result["by_class"]["question"]["count"] == 0


def test_unclear_fields_are_excluded_from_their_own_metrics_only() -> None:
    both = _p((True, "question"), (None, None), record_id="both", unclear=("has_misconception", "user_intent"))
    one = _p((True, "question"), (None, "question"), record_id="one", unclear=("has_misconception",))
    plain = _p((False, "question"), (False, "question"), record_id="plain")

    misconception = eval_module.misconception_metrics([both, one, plain])
    intent = eval_module.intent_metrics([both, one, plain])

    assert misconception["total"] == 1
    assert intent["total"] == 2
    assert sum(intent["confusion"]["question"].values()) == 2


def test_stability_lists_the_fields_whose_runs_disagree() -> None:
    result = eval_module.stability(
        [
            _p((True, "question"), (True, "question"), record_id="a", run=0),
            _p((True, "question"), (True, "question"), record_id="a", run=1),
            _p((True, "question"), (True, "question"), record_id="b", run=0),
            _p((False, "question"), (True, "question"), record_id="b", run=1),
            _p((True, "question"), (True, "question"), record_id="c", run=0),
        ]
    )

    assert result["records"] == 2
    assert result["unanimous"]["count"] == 1
    assert result["unstable"] == {"b": {"has_misconception": {"true": 1, "false": 1}}}


def test_stability_ignores_records_with_no_counted_field() -> None:
    both = ("has_misconception", "user_intent")
    result = eval_module.stability(
        [
            _p((True, "question"), (None, None), record_id="x", run=0, unclear=both),
            _p((False, "end_session"), (None, None), record_id="x", run=1, unclear=both),
            _p((True, "question"), (True, "question"), record_id="a", run=0),
            _p((True, "question"), (True, "question"), record_id="a", run=1),
        ]
    )

    assert result["records"] == 1
    assert result["unanimous"]["total"] == 1


async def test_classify_returns_the_two_fields() -> None:
    analysis = _analysis(user_intent="question", has_misconception=True, response_mode="reinforce", error_summary="x")
    trace = _trace_of(_source("a"))
    with patch("evals.map_turn_analysis.analyze_map_turn", AsyncMock(return_value=analysis)) as analyze:
        assert await eval_module.classify(trace) == {"has_misconception": True, "user_intent": "question"}
    state = analyze.await_args_list[0].args[0]
    assert state["topic"] == "スタック"


async def test_classify_retries_a_failed_analysis() -> None:
    analysis = _analysis()
    analyze = AsyncMock(side_effect=[None, analysis])
    with (
        patch("evals.map_turn_analysis.analyze_map_turn", analyze),
        patch("evals.map_turn_analysis._RETRY_BASE_DELAY_SECONDS", 0),
    ):
        assert await eval_module.classify(_trace_of(_source("a"))) == _OK
    assert analyze.await_count == 2


async def test_classify_gives_up_after_repeated_failures() -> None:
    with (
        patch("evals.map_turn_analysis.analyze_map_turn", AsyncMock(return_value=None)),
        patch("evals.map_turn_analysis._RETRY_BASE_DELAY_SECONDS", 0),
        pytest.raises(AnalysisFailed),
    ):
        await eval_module.classify(_trace_of(_source("a")))


def _trace_of(source: dict[str, Any]) -> SourceTrace:
    from evals.dataset import get_source_trace

    return get_source_trace(source["id"], {source["id"]: source})


async def test_run_keeps_real_and_handwritten_apart(tmp_path: Path) -> None:
    sources = {"r1": _source("r1", "実際の発言"), "r2": _source("r2", "実際の発言2")}
    dataset = _write(
        tmp_path / "d.jsonl",
        [
            _row("r1", _expected(False, "explanation")),
            _row("r2", _expected(False, "explanation")),
            _row(
                "hw1",
                _expected(True, "explanation"),
                source="handwritten",
                last="誤った発言",
                category="misconception",
                base="r1",
            ),
        ],
    )
    classifier = _by_message({"誤った発言": {"has_misconception": False, "user_intent": "explanation"}})

    assert await eval_module.run(eval_module.parse_args(_argv(tmp_path, dataset)), classifier, sources) == 0

    report = _report(tmp_path)
    assert set(report["by_source"]) == {"real", "handwritten"}
    assert "misconception" not in report and "intent" not in report
    real, handwritten = report["by_source"]["real"], report["by_source"]["handwritten"]
    assert real["misconception"]["total"] == 2
    assert real["misconception"]["accuracy"]["rate"] == 1.0
    assert handwritten["misconception"]["total"] == 1
    assert handwritten["misconception"]["missed"]["count"] == 1
    assert set(report["by_category"]) == {"misconception"}
    assert report["misjudged"] == ["hw1"]


async def test_run_omits_a_source_without_records(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "d.jsonl", [_row("r1", _expected(False, "explanation"))])

    assert (
        await eval_module.run(eval_module.parse_args(_argv(tmp_path, dataset)), _always_ok, {"r1": _source("r1")}) == 0
    )

    assert set(_report(tmp_path)["by_source"]) == {"real"}


async def test_run_skips_and_reports_unlabeled_unknown_and_blocked_rows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sources = {"ok": _source("ok"), "legacy": _source("legacy", route="legacy"), "todo": _source("todo")}
    dataset = _write(
        tmp_path / "d.jsonl",
        [
            _row("ok", _expected(False, "explanation")),
            _row("todo", None),
            _row("legacy", _expected(False, "explanation")),
            _row("gone", _expected(False, "explanation")),
        ],
    )

    assert await eval_module.run(eval_module.parse_args(_argv(tmp_path, dataset)), _always_ok, sources) == 0

    report = _report(tmp_path)
    assert report["meta"]["records"] == 1
    assert report["meta"]["skipped"]["unlabeled"] == ["todo"]
    assert set(report["meta"]["skipped"]["blocked"]) == {"legacy", "gone"}
    out = capsys.readouterr().out
    assert "gone" in out and "legacy" in out and "todo" in out


async def test_run_stops_when_nothing_is_labeled(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    dataset = _write(tmp_path / "d.jsonl", [_row("r1", None)])

    assert (
        await eval_module.run(eval_module.parse_args(_argv(tmp_path, dataset)), AsyncMock(), {"r1": _source("r1")})
        == 1
    )

    assert "正解の付いた行が無い" in capsys.readouterr().out


async def test_run_keeps_rows_with_both_fields_unclear_in_predictions_only(tmp_path: Path) -> None:
    dataset = _write(
        tmp_path / "d.jsonl",
        [_row("r1", _expected(None, None), unclear=["has_misconception", "user_intent"])],
    )

    assert (
        await eval_module.run(eval_module.parse_args(_argv(tmp_path, dataset)), _always_ok, {"r1": _source("r1")}) == 0
    )

    report = _report(tmp_path)
    real = report["by_source"]["real"]
    assert [p["record_id"] for p in report["predictions"]] == ["r1"]
    assert real["misconception"]["total"] == 0
    assert real["intent"]["total"] == 0
    assert real["stability"]["records"] == 0
    assert report["misjudged"] == []


async def test_resume_scores_against_the_labels_in_the_dataset_now(tmp_path: Path) -> None:
    sources = {"r1": _source("r1")}
    dataset = _write(tmp_path / "d.jsonl", [_row("r1", _expected(True, "explanation"))])
    argv = _argv(tmp_path, dataset)
    classifier = AsyncMock(return_value=dict(_OK))
    await eval_module.run(eval_module.parse_args(argv), classifier, sources)
    assert _report(tmp_path)["misjudged"] == ["r1"]

    _write(dataset, [_row("r1", _expected(False, "explanation"))])
    assert await eval_module.run(eval_module.parse_args(argv), classifier, sources) == 0

    assert classifier.await_count == 1
    assert _report(tmp_path)["misjudged"] == []


async def test_resume_reclassifies_when_the_input_changed(tmp_path: Path) -> None:
    row = _row("hw", _expected(False, "explanation"), source="handwritten")
    dataset = _write(tmp_path / "d.jsonl", [row | {"last_user_message": "前"}])
    sources = {"hw": _source("hw")}
    argv = _argv(tmp_path, dataset)
    classifier = AsyncMock(return_value=dict(_OK))
    await eval_module.run(eval_module.parse_args(argv), classifier, sources)

    _write(dataset, [row | {"last_user_message": "後"}])
    await eval_module.run(eval_module.parse_args(argv), classifier, sources)

    assert classifier.await_count == 2


async def test_run_filters_by_trace_and_source(tmp_path: Path) -> None:
    sources = {"r1": _source("r1"), "r2": _source("r2")}
    rows = [
        _row("r1", _expected(False, "explanation")),
        _row("r2", _expected(False, "explanation")),
        _row("hw", _expected(False, "explanation"), source="handwritten", base="r1"),
    ]
    dataset = _write(tmp_path / "d.jsonl", rows)
    seen: list[str] = []

    async def classifier(trace: SourceTrace) -> dict[str, Any]:
        seen.append(trace.input["conversation_history"][-1]["content"])
        return dict(_OK)

    await eval_module.run(
        eval_module.parse_args(_argv(tmp_path, dataset, "--source", "handwritten")), classifier, sources
    )
    assert seen == ["手書きの発言"]
    assert _report(tmp_path)["meta"]["records"] == 1

    args = eval_module.parse_args(_argv(tmp_path, dataset, "--trace", "missing"))
    assert await eval_module.run(args, classifier, sources) == 1


async def test_run_rejects_an_invalid_row(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "d.jsonl", [_row("r1", _expected(False, "chat"))])

    args = eval_module.parse_args(_argv(tmp_path, dataset))
    assert await eval_module.run(args, AsyncMock(), {"r1": _source("r1")}) == 1


async def test_run_stops_when_the_analysis_keeps_failing(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "d.jsonl", [_row("r1", _expected(False, "explanation"))])

    async def classifier(trace: SourceTrace) -> dict[str, Any]:
        raise AnalysisFailed("failed")

    args = eval_module.parse_args(_argv(tmp_path, dataset))
    assert await eval_module.run(args, classifier, {"r1": _source("r1")}) == 1


@pytest.fixture
def restore_models() -> Iterator[None]:
    response, structured = dict(RESPONSE_MODELS), dict(STRUCTURED_MODELS)
    yield
    RESPONSE_MODELS.clear()
    RESPONSE_MODELS.update(response)
    STRUCTURED_MODELS.clear()
    STRUCTURED_MODELS.update(structured)


async def _recording_classifier(trace: SourceTrace) -> dict[str, Any]:
    recorder = current_recorder()
    assert recorder is not None
    recorder.calls.append(
        {
            "task": "map-turn-analysis",
            "model": "gpt-6-luna",
            "input_tokens": 10,
            "cached_input_tokens": 0,
            "output_tokens": 5,
            "reasoning_tokens": 0,
            "seconds": 1.0,
        }
    )
    return dict(_OK)


async def test_report_carries_usage_models_and_hashes(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "d.jsonl", [_row("r1", _expected(False, "explanation"))])

    assert (
        await eval_module.run(
            eval_module.parse_args(_argv(tmp_path, dataset)), _recording_classifier, {"r1": _source("r1")}
        )
        == 0
    )

    meta = _report(tmp_path)["meta"]
    assert meta["kind"] == "map_turn_analysis"
    assert _report(tmp_path)["usage"]["tasks"]["map-turn-analysis"]["calls"] == 1
    assert meta["models"] == models_meta(MAP_TURN_ANALYSIS_TASKS)
    assert meta["model"] == asdict(STRUCTURED_MODELS["map-turn-analysis"])
    assert meta["dataset_sha256"] == sha256_bytes(dataset.read_bytes())
    assert meta["prompt_fingerprint"] == MAP_TURN_ANALYSIS_PROMPT_FINGERPRINT
    assert meta["labels_sha256"] and meta["inputs_sha256"]
    assert meta["phased"] is True


async def test_resume_keeps_saved_usage(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "d.jsonl", [_row("r1", _expected(False, "explanation"))])
    argv = _argv(tmp_path, dataset)
    sources = {"r1": _source("r1")}
    await eval_module.run(eval_module.parse_args(argv), _recording_classifier, sources)

    assert await eval_module.run(eval_module.parse_args(argv), AsyncMock(), sources) == 0

    assert _report(tmp_path)["usage"]["tasks"]["map-turn-analysis"]["calls"] == 1


async def test_override_is_recorded_and_changes_the_manifest(tmp_path: Path, restore_models: None) -> None:
    dataset = _write(tmp_path / "d.jsonl", [_row("r1", _expected(False, "explanation"))])
    sources = {"r1": _source("r1")}
    await eval_module.run(eval_module.parse_args(_argv(tmp_path, dataset)), _recording_classifier, sources)
    argv = _argv(tmp_path, dataset, "--model", "map-turn-analysis=openai:gpt-x")

    assert await eval_module.run(eval_module.parse_args(argv), _recording_classifier, sources) == 1

    argv = _argv(tmp_path, dataset, "--model", "map-turn-analysis=openai:gpt-x", checkpoint="ckpt2")
    assert await eval_module.run(eval_module.parse_args(argv), _recording_classifier, sources) == 0
    assert _report(tmp_path)["meta"]["models"]["map-turn-analysis"]["model"] == "gpt-x"


async def test_override_of_another_task_is_rejected(tmp_path: Path, restore_models: None) -> None:
    dataset = _write(tmp_path / "d.jsonl", [_row("r1", _expected(False, "explanation"))])
    argv = _argv(tmp_path, dataset, "--model", "learning-dialogue=openai:gpt-x")

    assert await eval_module.run(eval_module.parse_args(argv), _recording_classifier, {"r1": _source("r1")}) == 1


async def test_override_that_was_never_called_returns_1(tmp_path: Path, restore_models: None) -> None:
    dataset = _write(tmp_path / "d.jsonl", [_row("r1", _expected(False, "explanation"))])
    argv = _argv(tmp_path, dataset, "--model", "map-turn-analysis=openai:gpt-x")

    assert await eval_module.run(eval_module.parse_args(argv), _always_ok, {"r1": _source("r1")}) == 1
    assert (tmp_path / "report.json").exists()


async def test_classify_runs_the_phased_prompt_by_default_and_as_stored_with_no_phased() -> None:
    analyze = AsyncMock(return_value=_analysis())
    trace = _trace_of(_source("a"))
    with patch("evals.map_turn_analysis.analyze_map_turn", analyze):
        await eval_module.classify(trace)
        await eval_module.classify(trace, phased=False)

    phased_state, stored_state = (call.args[0] for call in analyze.await_args_list)
    assert phased_state["dialogue_phase"] == "free"
    assert stored_state.get("dialogue_phase") is None


async def test_classify_keeps_the_dialogue_phase_a_record_already_has() -> None:
    source = _source("a", dialogue_phase="questions")
    source["input"]["graph_state"]["dialogue_phase"] = "questions"
    analyze = AsyncMock(return_value=_analysis())
    with patch("evals.map_turn_analysis.analyze_map_turn", analyze):
        await eval_module.classify(_trace_of(source))

    assert analyze.await_args_list[0].args[0]["dialogue_phase"] == "questions"


async def test_no_phased_is_recorded_and_changes_the_input_hash_and_manifest(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "d.jsonl", [_row("r1", _expected(False, "explanation"))])
    sources = {"r1": _source("r1")}
    classifier = AsyncMock(return_value=dict(_OK))
    await eval_module.run(eval_module.parse_args(_argv(tmp_path, dataset)), classifier, sources)

    again = _argv(tmp_path, dataset, "--no-phased", checkpoint="ckpt2")
    assert await eval_module.run(eval_module.parse_args(again), classifier, sources) == 0
    unphased = _report(tmp_path)

    assert unphased["meta"]["phased"] is False
    stored = _argv(tmp_path, dataset, "--no-phased")
    assert await eval_module.run(eval_module.parse_args(stored), classifier, sources) == 1


async def test_rows_with_duplicate_ids_stop_the_run_before_any_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    row = _row("r1", _expected(False, "explanation"))
    dataset = _write(tmp_path / "d.jsonl", [row, row])
    classifier = AsyncMock()

    args = eval_module.parse_args(_argv(tmp_path, dataset))
    assert await eval_module.run(args, classifier, {"r1": _source("r1")}) == 1

    assert "r1" in capsys.readouterr().out
    classifier.assert_not_called()


async def test_a_row_without_the_expected_key_stops_the_run_with_its_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = _row("r1", _expected(False, "explanation"))
    del broken["expected"]
    dataset = _write(tmp_path / "d.jsonl", [broken])
    classifier = AsyncMock()

    args = eval_module.parse_args(_argv(tmp_path, dataset))
    assert await eval_module.run(args, classifier, {"r1": _source("r1")}) == 1

    assert "r1" in capsys.readouterr().out
    classifier.assert_not_called()


async def test_labels_hash_covers_only_the_rows_that_were_run(tmp_path: Path) -> None:
    sources = {"r1": _source("r1"), "r2": _source("r2")}
    rows = [
        _row("r1", _expected(False, "explanation")),
        _row("hw", None, source="handwritten", base="r2"),
    ]

    async def hashes(rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
        dataset = _write(tmp_path / f"{name}.jsonl", rows)
        argv = _argv(tmp_path, dataset, "--source", "real", checkpoint=name)
        await eval_module.run(eval_module.parse_args(argv), _always_ok, sources)
        meta: dict[str, Any] = _report(tmp_path)["meta"]
        return meta

    before = await hashes(rows, "a")
    labelled_elsewhere = [rows[0], {**rows[1], "expected": _expected(True, "question")}]
    after = await hashes(labelled_elsewhere, "b")
    relabelled = await hashes([_row("r1", _expected(True, "explanation")), rows[1]], "c")

    assert before["dataset_sha256"] != after["dataset_sha256"]
    assert before["labels_sha256"] == after["labels_sha256"]
    assert before["inputs_sha256"] == after["inputs_sha256"]
    assert before["labels_sha256"] != relabelled["labels_sha256"]


def test_validate_row_requires_the_expected_key() -> None:
    from evals.map_turn_analysis_dataset import validate_row

    row = _row("r1", None)
    del row["expected"]

    assert any("expected" in problem for problem in validate_row(row))
