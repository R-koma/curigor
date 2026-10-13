"""確認待ちの項目（`evals/pending/`）の形と、レポートとの照合。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from evals.dataset import load_golden_records
from evals.golden_yaml import dump_yaml
from evals.report import generations_from_report
from evals.verify import (
    FAILED,
    NOT_COVERED,
    PASSED,
    PENDING_DIR,
    TO_READ,
    UNCHECKED,
    check_item,
    document_problems,
    item_problems,
    load_pending,
    markdown_summary,
    verify,
)

CURRENT = {"map_prompt_fingerprint": "map-now", "prompt_fingerprint": "legacy-now"}
REGRESSION_RUN = {"mode": "regression", "replay_mode": "full", "route": "map", "runs": 3, "cascade": True}


def _run(
    index: int, verdicts: dict[str, str], *, output: str = "応答", analysis: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "run_index": index,
        "verdict": "pass" if all(v in ("pass", "na") for v in verdicts.values()) else "fail",
        "output": f"{output}{index}",
        "turn_analysis": analysis or {"response_mode": "expand"},
        "covered_aspects": [],
        "map_covered": [],
        "depth_map": None,
        "assertions": [
            {
                "assertion_id": assertion_id,
                "judged": verdict,
                "human": None,
                "detail": f"{assertion_id} の理由{index}",
                "decided_by": "screen",
            }
            for assertion_id, verdict in verdicts.items()
        ],
    }


def _record(trace: str, runs: list[dict[str, Any]], failure_mode: str = "fm") -> dict[str, Any]:
    return {"failure_mode": failure_mode, "source_trace_id": trace, "human_pass": None, "runs": runs}


def _report(records: list[dict[str, Any]], **meta: Any) -> dict[str, Any]:
    return {
        "meta": {
            "mode": "regression",
            "runs": 3,
            "replay_mode": "full",
            "route": "map",
            "traces": None,
            "map_prompt_fingerprint": "map-now",
            "prompt_fingerprint": "legacy-now",
            "judge": {"screen": "haiku", "confirm": "opus"},
        }
        | meta,
        "records": records,
    }


def _a1_report(passes_by_trace: dict[str, int], **meta: Any) -> dict[str, Any]:
    return _report(
        [
            _record(trace, [_run(i, {"a1": "pass" if i <= passes else "fail"}) for i in range(1, 4)])
            for trace, passes in passes_by_trace.items()
        ],
        **meta,
    )


def _item(**overrides: Any) -> dict[str, Any]:
    return {
        "id": "x",
        "run": REGRESSION_RUN,
        "target": {"failure_mode": "fm"},
        "value": "a1",
        "expect": {"passes": "all"},
        "status": UNCHECKED,
    } | overrides


def _check(item: dict[str, Any], report: dict[str, Any], tmp_path: Path) -> Any:
    return check_item(item, report, tmp_path / "report.json", current=CURRENT, evals_dir=tmp_path)


class TestPendingFiles:
    def test_every_pending_file_is_well_formed(self) -> None:
        problems = [p for path, document in load_pending(PENDING_DIR) for p in document_problems(path, document)]
        assert problems == []

    def test_targets_and_values_exist_in_the_golden(self) -> None:
        golden = {record["failure_mode"]: record for record in load_golden_records()}
        rubric_ids = {a["id"] for record in golden.values() for a in record["assertions"] if a["scope"] == "rubric"}
        problems: list[str] = []
        for path, document in load_pending(PENDING_DIR):
            for item in document["items"]:
                label = f"{path.name}#{item['id']}"
                failure_mode = item.get("target", {}).get("failure_mode")
                if failure_mode is not None and failure_mode not in golden:
                    problems.append(f"{label}: golden に無い failure_mode {failure_mode}")
                    continue
                if failure_mode is not None:
                    known = {i["source_trace_id"] for i in golden[failure_mode]["instances"]}
                    problems.extend(
                        f"{label}: {failure_mode} に無い trace {t}"
                        for t in item["target"].get("traces", []) + item["target"].get("exclude_traces", [])
                        if t not in known
                    )
                value = item.get("value")
                if value is None or value == "verdict" or "." in value:
                    continue
                own = {a["id"] for a in golden[failure_mode]["assertions"]} if failure_mode else rubric_ids
                if value not in own:
                    problems.append(f"{label}: 無い assertion {value}")
        assert problems == []


class TestItemProblems:
    def test_accepts_a_valid_item(self) -> None:
        assert item_problems(_item()) == []

    def test_read_and_expect_must_be_separate_items(self) -> None:
        assert any("別の項目" in p for p in item_problems(_item(read="本文を読む")))

    def test_a_fixed_number_needs_its_denominator(self) -> None:
        assert item_problems(_item(expect={"passes": 83})) != []

    def test_regression_needs_runs_and_replay_mode(self) -> None:
        run = {"mode": "regression", "route": "map", "cascade": True}
        problems = item_problems(_item(run=run))
        assert any("replay_mode" in p for p in problems) and any("runs" in p for p in problems)

    def test_turn_analysis_needs_the_expected_value(self) -> None:
        assert item_problems(_item(value="turn_analysis.selected_aspect")) != []

    def test_file_name_must_be_the_issue_number(self, tmp_path: Path) -> None:
        document = {"issue": 1, "summary": "s", "items": [_item()]}
        assert any("ファイル名" in p for p in document_problems(tmp_path / "2.yaml", document))


class TestNumericCheck:
    def test_all_runs_pass(self, tmp_path: Path) -> None:
        check = _check(_item(), _a1_report({"t1": 3}), tmp_path)
        assert check.status == PASSED

    def test_all_means_no_tolerance(self, tmp_path: Path) -> None:
        check = _check(_item(), _a1_report({"t1": 2}), tmp_path)
        assert check.status == FAILED
        assert "応答3" in check.details[0] and "a1 の理由3" in check.details[0]

    def test_a_fixed_number_allows_two_fewer_passes_by_default(self, tmp_path: Path) -> None:
        item = _item(expect={"passes": 5, "of": 6})
        assert _check(item, _a1_report({"t1": 2, "t2": 1}), tmp_path).status == PASSED
        assert _check(item, _a1_report({"t1": 1, "t2": 1}), tmp_path).status == FAILED

    def test_tolerance_can_be_overridden(self, tmp_path: Path) -> None:
        item = _item(expect={"passes": 5, "of": 6, "tolerance": 0})
        assert _check(item, _a1_report({"t1": 3, "t2": 1}), tmp_path).status == FAILED

    def test_a_different_denominator_is_not_covered(self, tmp_path: Path) -> None:
        check = _check(_item(expect={"passes": 5, "of": 6}), _a1_report({"t1": 3}), tmp_path)
        assert check.status == NOT_COVERED

    def test_not_applicable_runs_are_not_counted(self, tmp_path: Path) -> None:
        report = _report([_record("t1", [_run(1, {"a1": "pass"}), _run(2, {"a1": "na"}), _run(3, {"a1": "pass"})])])
        check = _check(_item(), report, tmp_path)
        assert check.status == PASSED and "2/2" in check.result

    def test_target_traces_and_exclusions(self, tmp_path: Path) -> None:
        report = _a1_report({"t1": 3, "t2": 0})
        assert _check(_item(target={"failure_mode": "fm", "traces": ["t1"]}), report, tmp_path).status == PASSED
        assert (
            _check(_item(target={"failure_mode": "fm", "exclude_traces": ["t2"]}), report, tmp_path).status == PASSED
        )

    def test_rubric_values_count_across_failure_modes(self, tmp_path: Path) -> None:
        report = _report(
            [
                _record("t1", [_run(i, {"r1": "pass"}) for i in range(1, 4)], "fm1"),
                _record(
                    "t2", [_run(i, {"r1": "fail" if i == 1 else "pass"}) for i in range(1, 4)], failure_mode="fm2"
                ),
            ]
        )
        check = _check(_item(target={}, value="r1", expect={"passes": 6, "of": 6}), report, tmp_path)
        assert check.status == PASSED and "r1 5/6" in check.result

    def test_turn_analysis_value(self, tmp_path: Path) -> None:
        report = _report(
            [_record("t1", [_run(i, {"a1": "pass"}, analysis={"selected_aspect": "明暗法"}) for i in range(1, 4)])]
        )
        item = _item(value="turn_analysis.selected_aspect", equals="明暗法")
        assert _check(item, report, tmp_path).status == PASSED
        assert _check(item | {"equals": "遠近法"}, report, tmp_path).status == FAILED


class TestScoring:
    def _scoring_report(self) -> dict[str, Any]:
        run = _run(1, {"a1": "fail"})
        run["assertions"][0]["human"] = "fail"
        other = _run(1, {"a1": "pass"})
        other["assertions"][0]["human"] = "fail"
        report = _report([_record("t1", [run]), _record("t2", [other])], mode="scoring", runs=1, replay_mode=None)
        report["agreement"] = {"calibration": {"final": {"passed": False, "failures": ["TPR 50% が閾値 90% 未満"]}}}
        return report

    def test_scoring_counts_agreement_with_the_human_labels(self, tmp_path: Path) -> None:
        item = _item(run={"mode": "scoring", "route": "map", "cascade": True})
        check = _check(item, self._scoring_report(), tmp_path)
        assert check.status == FAILED and "a1 1/2" in check.result

    def test_calibration_gate(self, tmp_path: Path) -> None:
        item = _item(run={"mode": "scoring", "route": "map", "cascade": True}, value="calibration.final")
        check = _check(item, self._scoring_report(), tmp_path)
        assert check.status == FAILED and "TPR 50%" in check.result


class TestNotCovered:
    def test_screen_only_report_suggests_rescoring_it(self, tmp_path: Path) -> None:
        report = _a1_report({"t1": 3}, judge={"screen": "haiku", "confirm": None})
        check = _check(_item(), report, tmp_path)
        assert check.status == NOT_COVERED
        assert check.commands == [f"uv run python -m evals.eval --rescore-report {tmp_path / 'report.json'}"]

    def test_an_older_prompt_needs_a_new_run(self, tmp_path: Path) -> None:
        check = _check(_item(), _a1_report({"t1": 3}, map_prompt_fingerprint="map-old"), tmp_path)
        assert check.status == NOT_COVERED and "map-old" in check.result
        assert check.commands == ["uv run python -m evals.eval --mode regression --route map --runs 3"]

    def test_runs_and_route_must_match(self, tmp_path: Path) -> None:
        assert _check(_item(), _a1_report({"t1": 3}, runs=5), tmp_path).status == NOT_COVERED
        assert _check(_item(), _a1_report({"t1": 3}, route="all"), tmp_path).status == NOT_COVERED

    def test_a_traced_report_does_not_cover_a_full_target(self, tmp_path: Path) -> None:
        check = _check(_item(), _a1_report({"t1": 3}, traces=["t1"]), tmp_path)
        assert check.status == NOT_COVERED

    def test_missing_traces_are_named_with_a_command_for_them(self, tmp_path: Path) -> None:
        item = _item(target={"failure_mode": "fm", "traces": ["t9"]})
        check = _check(item, _a1_report({"t1": 3}), tmp_path)
        assert check.status == NOT_COVERED and "t9" in check.result
        assert check.commands[0].endswith("--trace t9")


class TestBaseline:
    def _write(self, tmp_path: Path, report: dict[str, Any]) -> None:
        (tmp_path / "baselines").mkdir(exist_ok=True)
        (tmp_path / "baselines" / "base.json").write_text(json.dumps(report), encoding="utf-8")

    def test_no_worse_than_the_baseline_within_two(self, tmp_path: Path) -> None:
        self._write(tmp_path, _a1_report({"t1": 3, "t2": 3}, map_prompt_fingerprint="map-old"))
        item = _item(expect={"baseline": "baselines/base.json"})
        assert _check(item, _a1_report({"t1": 2, "t2": 2}), tmp_path).status == PASSED

    def test_three_fewer_fails_and_shows_only_the_instances_that_dropped(self, tmp_path: Path) -> None:
        self._write(tmp_path, _a1_report({"t1": 3, "t2": 0}))
        item = _item(expect={"baseline": "baselines/base.json"})
        check = _check(item, _a1_report({"t1": 0, "t2": 0}), tmp_path)
        assert check.status == FAILED
        assert len(check.details) == 3 and all("fm/t1" in d for d in check.details)

    def test_only_instances_in_both_reports_are_compared(self, tmp_path: Path) -> None:
        self._write(tmp_path, _a1_report({"t1": 3}))
        item = _item(expect={"baseline": "baselines/base.json"})
        check = _check(item, _a1_report({"t1": 3, "t2": 0}), tmp_path)
        assert check.status == PASSED and "a1 3/3" in check.result

    def test_a_screen_only_baseline_is_rescored_first(self, tmp_path: Path) -> None:
        self._write(tmp_path, _a1_report({"t1": 3}, judge={"screen": "haiku", "confirm": None}))
        item = _item(expect={"baseline": "baselines/base.json"})
        check = _check(item, _a1_report({"t1": 3}), tmp_path)
        assert check.status == NOT_COVERED and "--rescore-report" in check.commands[0]

    def test_a_missing_baseline_is_not_covered(self, tmp_path: Path) -> None:
        item = _item(expect={"baseline": "baselines/none.json"})
        assert _check(item, _a1_report({"t1": 3}), tmp_path).status == NOT_COVERED


class TestReadItems:
    def test_lists_every_run_for_a_person_to_read(self, tmp_path: Path) -> None:
        item = _item(read="答えに触れてから移る")
        del item["expect"]
        check = _check(item, _a1_report({"t1": 3}), tmp_path)
        assert check.status == TO_READ
        assert len(check.details) == 3 and "応答1" in check.details[0]


class TestVerify:
    def _setup(self, tmp_path: Path, items: list[dict[str, Any]], report: dict[str, Any]) -> tuple[Path, Path]:
        pending = tmp_path / "pending"
        pending.mkdir()
        path = pending / "1.yaml"
        path.write_text(dump_yaml({"issue": 1, "summary": "変更", "items": items}), encoding="utf-8")
        report_path = tmp_path / "r.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        return path, report_path

    def test_writes_the_result_back_and_skips_settled_items(self, tmp_path: Path) -> None:
        settled = _item(id="done", status=PASSED, result="前の結果")
        path, report_path = self._setup(tmp_path, [_item(), settled], _a1_report({"t1": 3}))
        verify(report_path, pending_dir=path.parent, current=CURRENT, today=date(2026, 10, 13))
        items = yaml.safe_load(path.read_text(encoding="utf-8"))["items"]
        assert items[0]["status"] == PASSED
        assert items[0]["checked_on"] == date(2026, 10, 13) and items[0]["report"] == "r.json"
        assert items[1]["result"] == "前の結果"

    def test_a_read_item_keeps_its_report_when_a_later_report_does_not_cover_it(self, tmp_path: Path) -> None:
        item = _item(status=TO_READ, report="old.json", read="読む")
        del item["expect"]
        path, report_path = self._setup(tmp_path, [item], _a1_report({"t1": 3}, runs=5))
        verify(report_path, pending_dir=path.parent, current=CURRENT)
        assert yaml.safe_load(path.read_text(encoding="utf-8"))["items"][0]["report"] == "old.json"

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        path, report_path = self._setup(tmp_path, [_item()], _a1_report({"t1": 3}))
        before = path.read_text(encoding="utf-8")
        verify(report_path, pending_dir=path.parent, current=CURRENT, write=False)
        assert path.read_text(encoding="utf-8") == before

    def test_a_malformed_file_stops_the_run(self, tmp_path: Path) -> None:
        path, report_path = self._setup(tmp_path, [_item(status="済み")], _a1_report({"t1": 3}))
        with pytest.raises(SystemExit):
            verify(report_path, pending_dir=path.parent, current=CURRENT)

    def test_markdown_summary_escapes_pipes(self) -> None:
        summary = markdown_summary({"issue": 1, "summary": "変更", "items": [_item(result="a | b")]})
        assert "a \\| b" in summary and summary.startswith("## #1 変更")


def test_generations_from_report_round_trips_the_saved_responses() -> None:
    report = _a1_report({"t1": 3})
    generations = generations_from_report(report)
    assert sorted(generations[("fm", "t1")]) == [1, 2, 3]
    assert generations[("fm", "t1")][2].output == "応答2"


def test_generations_from_report_rejects_a_scoring_report() -> None:
    with pytest.raises(ValueError):
        generations_from_report(_a1_report({"t1": 3}, mode="scoring"))
