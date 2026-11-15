import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from evals.compare import (
    comparability,
    compare,
    main,
    model_diff,
    paired_delta,
    print_comparison,
    record_scores,
    report_kind,
)
from evals.map_turn_analysis import Prediction, intent_metrics
from evals.map_turn_analysis_dataset import USER_INTENTS

BASELINES = Path(__file__).parents[3] / "evals" / "baselines"
V = {"fm/t1": ["pass", "fail", "pass"], "fm/t2": ["pass", "pass", "pass"]}
BASE = {f"r{i}": float(i % 2) for i in range(10)}
CAND = {f"r{i}": float((i + 1) % 3 == 0) for i in range(10)}

_USAGE: dict[str, Any] = {
    "tasks": {"learning-dialogue": {"calls": 6, "cost_per_call_usd": 0.001, "seconds_p50": 2.0, "seconds_p95": 4.0}},
    "estimated_cost_usd": 0.006,
    "unpriced_models": [],
}


def _eval_report(verdicts: dict[str, list[str]], **meta: Any) -> dict[str, Any]:
    base_meta: dict[str, Any] = {
        "mode": "regression",
        "runs": 3,
        "replay_mode": "full",
        "route": "map",
        "traces": None,
        "model": "gpt-6-luna",
        "temperature": 0.7,
        "models": {"learning-dialogue": {"provider": "openai", "model": "gpt-6-luna", "temperature": 0.7}},
        "prompt_fingerprint": "p",
        "map_prompt_fingerprint": "m",
        "judge": {"screen": "a", "confirm": "b"},
        "check_fingerprints": {"c": "1"},
        "dataset_content_sha256": "d",
    }
    records: list[dict[str, Any]] = []
    for key, runs in verdicts.items():
        failure_mode, trace = key.split("/")
        records.append(
            {
                "failure_mode": failure_mode,
                "source_trace_id": trace,
                "runs": [{"run_index": i, "verdict": verdict} for i, verdict in enumerate(runs, start=1)],
            }
        )
    passes = [run["verdict"] == "pass" for record in records for run in record["runs"]]
    return {
        "meta": {**base_meta, **meta},
        "records": records,
        "aggregate": {
            "failure_mode_pass_rates": [{"failure_mode": "fm", "pass_rate": sum(passes) / len(passes)}],
            "rubric_pass_rates": [{"assertion_id": "r1", "pass_rate": 0.9}],
        },
        "usage": json.loads(json.dumps(_USAGE)),
    }


def _feedback_report(predictions: list[tuple[str, str, str | None]], **meta: Any) -> dict[str, Any]:
    return {
        "meta": {
            "kind": "feedback",
            "mode": "regression",
            "runs": 1,
            "prompt_fingerprint": "p",
            "dataset_sha256": "d",
            "models": {"analyze-dialogue": {"provider": "openai", "model": "gpt-6-luna"}},
            **meta,
        },
        "predictions": [
            {"record_id": rid, "run": 0, "level": level, "human_level": human} for rid, level, human in predictions
        ],
        "stability": {"unanimous": {"rate": 1.0}},
        "usage": json.loads(json.dumps(_USAGE)),
    }


def _review_report(predictions: list[tuple[str, bool, bool]], **meta: Any) -> dict[str, Any]:
    return {
        "meta": {
            "kind": "review_end",
            "runs": 1,
            "prompt_fingerprint": "p",
            "dataset_sha256": "d",
            "model": {"provider": "openai", "model": "gpt-6-luna"},
            **meta,
        },
        "predictions": [
            {"record_id": rid, "run": 0, "predicted": predicted, "expected": expected}
            for rid, predicted, expected in predictions
        ],
        "stability": {"unanimous": {"rate": 1.0}},
    }


def _map_prediction(
    record_id: str,
    source: str,
    predicted: tuple[bool, str],
    expected: tuple[bool | None, str | None],
    *,
    run: int = 0,
    unclear: tuple[str, ...] = (),
) -> Prediction:
    return Prediction(
        record_id=record_id,
        source=source,
        category=None,
        run=run,
        predicted={"has_misconception": predicted[0], "user_intent": predicted[1]},
        expected={"has_misconception": expected[0], "user_intent": expected[1]},
        unclear=unclear,
    )


def _map_report(predictions: list[Prediction], **meta: Any) -> dict[str, Any]:
    sources = sorted({p.source for p in predictions})
    return {
        "meta": {
            "kind": "map_turn_analysis",
            "runs": 1,
            "prompt_fingerprint": "p",
            "phased": True,
            "dataset_sha256": "d",
            "labels_sha256": "l",
            "inputs_sha256": "i",
            "models": {"map-turn-analysis": {"provider": "openai", "model": "gpt-6-luna"}},
            **meta,
        },
        "by_source": {
            source: {"intent": intent_metrics(p for p in predictions if p.source == source)} for source in sources
        },
        "predictions": [asdict(p) for p in predictions],
        "usage": json.loads(json.dumps(_USAGE)),
    }


def _set(source: str = "real", *, flagged: bool | None = None, intent: str = "explanation") -> list[Prediction]:
    """r0〜r9 は誤りあり、r10〜r19 は誤りなし。flagged が None なら誤りの判定は全件正しく、真偽なら全件その判定。"""
    return [
        _map_prediction(
            f"{source}{i}", source, (i < 10 if flagged is None else flagged, intent), (i < 10, "explanation")
        )
        for i in range(20)
    ]


def test_paired_delta_detects_clear_improvement() -> None:
    base = {f"r{i}": 0.0 for i in range(20)}
    cand = {f"r{i}": 1.0 for i in range(20)}

    result = paired_delta(base, cand)

    assert result["delta"] == 1.0 and result["ci95"] == [1.0, 1.0] and result["verdict"] == "improved"


def test_paired_delta_lower_is_better_flips_verdict() -> None:
    base = {f"r{i}": 0.0 for i in range(20)}
    cand = {f"r{i}": 1.0 for i in range(20)}

    assert paired_delta(base, cand, higher_is_better=False)["verdict"] == "regressed"


def test_paired_delta_mixed_changes_are_within_noise() -> None:
    base = {f"r{i}": 0.5 for i in range(20)}
    cand = {f"r{i}": (1.0 if i % 2 else 0.0) for i in range(20)}

    result = paired_delta(base, cand)

    assert result["delta"] == 0.0 and result["verdict"] == "within_noise"


def test_paired_delta_is_reproducible() -> None:
    assert paired_delta(BASE, CAND) == paired_delta(BASE, CAND)


def test_paired_delta_without_records() -> None:
    assert paired_delta({}, {}) == {
        "records": 0,
        "base": None,
        "candidate": None,
        "delta": None,
        "ci95": None,
        "verdict": "within_noise",
    }


def test_paired_delta_uses_only_records_in_both() -> None:
    result = paired_delta({"a": 0.0, "b": 0.0}, {"b": 1.0, "c": 1.0})

    assert result["records"] == 1 and result["delta"] == 1.0


def test_eval_all_pass_is_share_of_passing_runs() -> None:
    assert record_scores(_eval_report({"fm/t1": ["pass", "fail", "pass"]}), "all_pass") == {
        "fm/t1": pytest.approx(2 / 3)
    }


def test_feedback_metrics_use_labeled_records_only() -> None:
    report = _feedback_report(
        [("a", "low", "low"), ("b", "medium", "low"), ("c", "high", None), ("d", "high", "medium")]
    )

    assert record_scores(report, "exact") == {"a": 1.0, "b": 0.0, "d": 0.0}
    assert record_scores(report, "low_overrated") == {"a": 0.0, "b": 1.0}


def test_review_end_false_and_missed_end_use_their_subsets() -> None:
    report = _review_report([("a", True, False), ("b", False, False), ("c", False, True), ("d", True, True)])

    assert record_scores(report, "accuracy") == {"a": 0.0, "b": 1.0, "c": 0.0, "d": 1.0}
    assert record_scores(report, "false_end") == {"a": 1.0, "b": 0.0}
    assert record_scores(report, "missed_end") == {"c": 1.0, "d": 0.0}


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("runs", 5),
        ("route", "all"),
        ("map_prompt_fingerprint", "x"),
        ("dataset_content_sha256", "x"),
        ("judge", {"screen": "a", "confirm": None}),
    ],
)
def test_different_conditions_block(key: str, value: Any) -> None:
    blockers, _ = comparability(_eval_report(V), _eval_report(V, **{key: value}))

    assert any(key in blocker for blocker in blockers)


def test_different_feedback_conditions_block() -> None:
    blockers, _ = comparability(
        _feedback_report([("a", "low", "low")]), _feedback_report([("a", "low", "low")], dataset_sha256="x")
    )

    assert any("dataset_sha256" in blocker for blocker in blockers)


def test_different_kinds_block() -> None:
    blockers, _ = comparability(_eval_report(V), _feedback_report([("a", "low", "low")]))

    assert any("種類" in blocker for blocker in blockers)


def test_scoring_report_blocks() -> None:
    blockers, _ = comparability(_eval_report(V, mode="scoring"), _eval_report(V))

    assert any("regression" in blocker for blocker in blockers)


def test_missing_record_blocks() -> None:
    blockers, _ = comparability(_eval_report(V), _eval_report({"fm/t1": V["fm/t1"]}))

    assert any("fm/t2" in blocker for blocker in blockers)


def test_unequal_run_counts_block() -> None:
    blockers, _ = comparability(_eval_report({"fm/t1": ["pass"] * 3}), _eval_report({"fm/t1": ["pass"] * 2}))

    assert any("run の数" in blocker for blocker in blockers)


def test_old_baseline_warns_instead_of_blocking() -> None:
    old = _eval_report(V)
    for key in ("models", "dataset_content_sha256"):
        old["meta"].pop(key)
    old.pop("usage")

    blockers, warnings = comparability(old, _eval_report(V))

    assert blockers == [] and len(warnings) >= 2
    assert compare(old, _eval_report(V))["usage"] is None


def test_model_diff_lists_only_changed_tasks() -> None:
    base = _eval_report(V, models={"a": {"model": "x"}, "b": {"model": "y"}})
    candidate = _eval_report(V, models={"a": {"model": "x"}, "b": {"model": "z"}})

    assert model_diff(base, candidate) == {"b": {"base": {"model": "y"}, "candidate": {"model": "z"}}}


def test_old_baseline_models_compare_on_shared_keys() -> None:
    old = _eval_report(V)
    old["meta"].pop("models")

    assert model_diff(old, _eval_report(V)) == {}


def test_same_models_warn_as_noise_measurement() -> None:
    _, warnings = comparability(_eval_report(V), _eval_report(V))

    assert any("揺れの幅" in warning for warning in warnings)


def test_usage_ratio() -> None:
    candidate = _eval_report(V)
    candidate["usage"]["tasks"]["learning-dialogue"]["cost_per_call_usd"] = 0.004

    cost = compare(_eval_report(V), candidate)["usage"]["tasks"]["learning-dialogue"]["cost_per_call_usd"]

    assert cost["ratio"] == pytest.approx(4.0)


def test_usage_ratio_is_none_when_a_side_has_no_price() -> None:
    candidate = _eval_report(V)
    candidate["usage"]["tasks"]["learning-dialogue"]["cost_per_call_usd"] = None

    cost = compare(_eval_report(V), candidate)["usage"]["tasks"]["learning-dialogue"]["cost_per_call_usd"]

    assert cost["ratio"] is None


def test_compare_lists_regressed_and_improved_records() -> None:
    base = _eval_report({"fm/t1": ["pass"] * 3, "fm/t2": ["fail"] * 3})
    candidate = _eval_report({"fm/t1": ["fail"] * 3, "fm/t2": ["pass"] * 3})

    breakdown = compare(base, candidate)["breakdown"]

    assert [row["record"] for row in breakdown["regressed_records"]] == ["fm/t1"]
    assert [row["record"] for row in breakdown["improved_records"]] == ["fm/t2"]


def test_main_returns_1_on_blockers_and_0_with_force(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base, candidate, out = tmp_path / "b.json", tmp_path / "c.json", tmp_path / "out.json"
    base.write_text(json.dumps(_eval_report(V)), encoding="utf-8")
    candidate.write_text(json.dumps(_eval_report(V, route="all")), encoding="utf-8")

    assert main([str(base), str(candidate)]) == 1
    assert "route" in capsys.readouterr().out
    assert main([str(base), str(candidate), "--force", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["kind"] == "eval"


def test_main_never_compares_different_kinds(tmp_path: Path) -> None:
    base, candidate = tmp_path / "b.json", tmp_path / "c.json"
    base.write_text(json.dumps(_eval_report(V)), encoding="utf-8")
    candidate.write_text(json.dumps(_feedback_report([("a", "low", "low")])), encoding="utf-8")

    assert main([str(base), str(candidate), "--force"]) == 1


def test_unknown_report_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="種類"):
        report_kind({"meta": {"kind": "other"}})


def test_print_comparison_leads_with_the_primary_metric(capsys: pytest.CaptureFixture[str]) -> None:
    result = compare(_eval_report(V), _eval_report({"fm/t1": ["pass"] * 3, "fm/t2": ["pass"] * 3}))

    print_comparison(result)

    out = capsys.readouterr().out
    assert "all_pass" in out and "95% 区間" in out and "料金と時間" in out


def test_print_comparison_says_no_usage_for_old_reports(capsys: pytest.CaptureFixture[str]) -> None:
    old = _eval_report(V)
    old.pop("usage")

    print_comparison(compare(old, _eval_report(V)))

    assert "記録なし" in capsys.readouterr().out


def test_reads_committed_baseline() -> None:
    report = json.loads((BASELINES / "map-v6-full.json").read_text(encoding="utf-8"))

    result = compare(report, report)

    assert result["metrics"]["all_pass"]["delta"] == 0.0
    assert result["metrics"]["all_pass"]["verdict"] == "within_noise"
    assert result["usage"] is None


def test_baselines_with_different_prompts_block() -> None:
    v5 = json.loads((BASELINES / "map-v5-full.json").read_text(encoding="utf-8"))
    v6 = json.loads((BASELINES / "map-v6-full.json").read_text(encoding="utf-8"))

    blockers, _ = comparability(v5, v6)

    assert any("map_prompt_fingerprint" in blocker for blocker in blockers)


def test_zero_difference_is_printed_without_a_sign(capsys: pytest.CaptureFixture[str]) -> None:
    report = _eval_report(V)

    print_comparison(compare(report, report))

    out = capsys.readouterr().out
    assert "差 0.0 ポイント" in out and "−0.0" not in out and "+0.0" not in out


@pytest.mark.parametrize("count", [1, 2, 9])
def test_few_records_are_not_judged(count: int) -> None:
    base = {f"r{i}": 0.0 for i in range(count)}
    cand = {f"r{i}": 1.0 for i in range(count)}

    result = paired_delta(base, cand)

    assert result["verdict"] == "too_few_records"
    assert result["delta"] == 1.0 and result["ci95"] is not None


def test_ten_uniformly_improved_records_are_judged() -> None:
    base = {f"r{i}": 0.0 for i in range(10)}
    cand = {f"r{i}": 1.0 for i in range(10)}

    assert paired_delta(base, cand)["verdict"] == "improved"


def test_print_comparison_says_too_few_records(capsys: pytest.CaptureFixture[str]) -> None:
    base = _eval_report({"fm/t1": ["fail"] * 3})
    candidate = _eval_report({"fm/t1": ["pass"] * 3})

    print_comparison(compare(base, candidate))

    assert "件数が少なく判定しない（1 レコード）" in capsys.readouterr().out


def test_unpriced_candidate_is_not_printed_as_free(capsys: pytest.CaptureFixture[str]) -> None:
    candidate = _eval_report(V)
    candidate["usage"]["tasks"]["learning-dialogue"]["cost_per_call_usd"] = None

    print_comparison(compare(_eval_report(V), candidate))

    out = capsys.readouterr().out
    assert "$0.00000" not in out and "料金不明" in out


def test_missing_seconds_are_printed_as_no_record(capsys: pytest.CaptureFixture[str]) -> None:
    candidate = _eval_report(V)
    candidate["usage"]["tasks"]["learning-dialogue"]["seconds_p50"] = None

    print_comparison(compare(_eval_report(V), candidate))

    out = capsys.readouterr().out
    assert "0.0s" not in out and "記録なし" in out


def test_unpriced_task_warns() -> None:
    candidate = _eval_report(V)
    candidate["usage"]["tasks"]["learning-dialogue"]["cost_per_call_usd"] = None

    _, warnings = comparability(_eval_report(V), candidate)

    assert any("料金不明" in warning and "learning-dialogue" in warning for warning in warnings)


def test_map_turn_analysis_record_scores_use_the_matching_subsets() -> None:
    report = _map_report(
        [
            _map_prediction("a", "real", (True, "question"), (True, "question")),
            _map_prediction("a", "real", (False, "question"), (True, "question"), run=1),
            _map_prediction("b", "real", (True, "exhausted"), (False, "end_session")),
            _map_prediction("h", "handwritten", (True, "question"), (True, "question")),
        ]
    )

    assert record_scores(report, "real.misconception_accuracy") == {"a": 0.5, "b": 0.0}
    assert record_scores(report, "real.intent_accuracy") == {"a": 1.0, "b": 0.0}
    assert record_scores(report, "real.missed_misconception") == {"a": 0.5}
    assert record_scores(report, "real.false_alarm") == {"b": 1.0}
    assert record_scores(report, "handwritten.misconception_accuracy") == {"h": 1.0}


def test_map_turn_analysis_scores_skip_unclear_fields() -> None:
    report = _map_report(
        [
            _map_prediction("a", "real", (True, "question"), (None, "question"), unclear=("has_misconception",)),
            _map_prediction(
                "b", "real", (True, "question"), (None, None), unclear=("has_misconception", "user_intent")
            ),
        ]
    )

    assert record_scores(report, "real.misconception_accuracy") == {}
    assert record_scores(report, "real.intent_accuracy") == {"a": 1.0}
    assert record_scores(report, "real.missed_misconception") == {}


def test_map_turn_analysis_compare_reports_each_source_metric() -> None:
    base = _map_report(_set(flagged=True))
    candidate = _map_report(_set())

    result = compare(base, candidate)

    assert result["blockers"] == []
    assert result["primary"] == "real.missed_misconception"
    assert set(result["metrics"]) == {
        "real.misconception_accuracy",
        "real.intent_accuracy",
        "real.missed_misconception",
        "real.false_alarm",
    }
    assert result["metrics"]["real.false_alarm"]["verdict"] == "improved"
    assert result["metrics"]["real.false_alarm"]["records"] == 10
    assert result["metrics"]["real.missed_misconception"]["verdict"] == "within_noise"
    assert result["metrics"]["real.misconception_accuracy"]["verdict"] == "improved"
    assert result["metrics"]["real.misconception_accuracy"]["records"] == 20
    assert result["metrics"]["real.intent_accuracy"]["verdict"] == "within_noise"


def test_map_turn_analysis_does_not_judge_a_subset_under_ten_records() -> None:
    few = [_map_prediction(f"r{i}", "real", (True, "explanation"), (i < 6, "explanation")) for i in range(12)]
    perfect = [_map_prediction(f"r{i}", "real", (i < 6, "explanation"), (i < 6, "explanation")) for i in range(12)]

    result = compare(_map_report(few), _map_report(perfect))

    assert result["metrics"]["real.false_alarm"]["verdict"] == "too_few_records"


def test_map_turn_analysis_lower_is_better_metrics_flip_the_direction() -> None:
    result = compare(_map_report(_set()), _map_report(_set(flagged=True)))

    assert result["metrics"]["real.false_alarm"]["delta"] > 0
    assert result["metrics"]["real.false_alarm"]["verdict"] == "regressed"
    assert result["metrics"]["real.misconception_accuracy"]["verdict"] == "regressed"


def test_map_turn_analysis_improved_when_a_lower_is_better_metric_drops() -> None:
    wrong = [_map_prediction(f"real{i}", "real", (False, "explanation"), (True, "explanation")) for i in range(12)]
    right = [_map_prediction(f"real{i}", "real", (True, "explanation"), (True, "explanation")) for i in range(12)]

    result = compare(_map_report(wrong), _map_report(right))

    assert result["metrics"]["real.missed_misconception"]["verdict"] == "improved"
    assert result["metrics"]["real.false_alarm"]["records"] == 0


def test_map_turn_analysis_without_handwritten_rows_has_no_handwritten_metrics() -> None:
    result = compare(_map_report(_set()), _map_report(_set()))

    assert not any(name.startswith("handwritten.") for name in result["metrics"])


def test_map_turn_analysis_falls_back_to_handwritten_when_there_is_no_real_source() -> None:
    result = compare(_map_report(_set("handwritten")), _map_report(_set("handwritten")))

    assert result["primary"] == "handwritten.missed_misconception"
    assert not any(name.startswith("real.") for name in result["metrics"])


def test_map_turn_analysis_never_pools_real_and_handwritten() -> None:
    both = _set("real") + _set("handwritten", flagged=True)

    result = compare(_map_report(both), _map_report(both))

    assert result["metrics"]["real.misconception_accuracy"]["records"] == 20
    assert result["metrics"]["handwritten.misconception_accuracy"]["records"] == 20
    assert all("." in name for name in result["metrics"])


@pytest.mark.parametrize("key", ["labels_sha256", "inputs_sha256", "prompt_fingerprint", "phased", "runs"])
def test_map_turn_analysis_different_conditions_block(key: str) -> None:
    other = {"runs": 5, "phased": False}.get(key, "x")
    blockers, _ = comparability(_map_report(_set()), _map_report(_set(), **{key: other}))

    assert any(key in blocker for blocker in blockers)


def test_map_turn_analysis_different_records_block() -> None:
    blockers, _ = comparability(_map_report(_set()), _map_report(_set()[:15]))

    assert any("片方にしか無い" in blocker for blocker in blockers)


def test_map_turn_analysis_is_not_comparable_with_other_kinds() -> None:
    blockers, _ = comparability(_map_report(_set()), _review_report([("a", True, True)]))

    assert any("種類" in blocker for blocker in blockers)


def test_map_turn_analysis_breakdown_lists_the_accuracy_of_each_intent() -> None:
    breakdown = compare(_map_report(_set(intent="question")), _map_report(_set()))["breakdown"]

    rows = {row["name"]: row for row in breakdown["intent_by_class"]["real"]}
    assert set(rows) == set(USER_INTENTS)
    assert rows["explanation"]["base"] == 0.0 and rows["explanation"]["candidate"] == 1.0
    assert rows["question"]["base"] is None


def test_map_turn_analysis_print_leads_with_the_primary_and_shows_the_breakdown(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = compare(_map_report(_set(flagged=True)), _map_report(_set()))

    print_comparison(result)

    out = capsys.readouterr().out
    assert out.index("real.missed_misconception") < out.index("real.false_alarm")
    assert "発言の種類ごとの正解率" in out
    assert "explanation" in out


def test_map_turn_analysis_main_compares_two_reports(tmp_path: Path) -> None:
    base, candidate = tmp_path / "base.json", tmp_path / "candidate.json"
    base.write_text(json.dumps(_map_report(_set(flagged=True))), encoding="utf-8")
    candidate.write_text(json.dumps(_map_report(_set())), encoding="utf-8")

    assert main([str(base), str(candidate)]) == 0


def test_map_turn_analysis_a_changed_dataset_file_alone_does_not_block() -> None:
    blockers, _ = comparability(_map_report(_set()), _map_report(_set(), dataset_sha256="other"))

    assert blockers == []


def test_map_turn_analysis_leads_with_missed_and_prints_the_four_metrics_in_order(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = compare(_map_report(_set(flagged=True)), _map_report(_set()))

    print_comparison(result)

    out = capsys.readouterr().out
    order = ["missed_misconception", "false_alarm", "intent_accuracy", "misconception_accuracy"]
    positions = [out.index(f"real.{name}") for name in order]
    assert positions == sorted(positions)
    assert list(result["metrics"])[:4] == [f"real.{name}" for name in order]


def test_map_turn_analysis_primary_separates_missing_everything_from_flagging_everything() -> None:
    miss_all = _map_report(_set(flagged=False))
    flag_all = _map_report(_set(flagged=True))

    result = compare(miss_all, flag_all)

    assert result["metrics"]["real.misconception_accuracy"]["delta"] == 0
    assert result["primary"] == "real.missed_misconception"
    assert result["metrics"][result["primary"]]["verdict"] == "improved"
