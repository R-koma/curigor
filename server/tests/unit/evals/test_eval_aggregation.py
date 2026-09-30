"""eval.py の集計・一致率・入力変換の純関数。

judge 呼び出しと生成は API を叩くので対象外。ここで守るのは、この eval が出す数字そのもの
（混同行列・pass 率・レコード単位の集約）と、na を分母から外す扱い。
"""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from evals.eval import (
    AssertionOutcome,
    Generation,
    InstanceResult,
    RunResult,
    SourceTrace,
    aggregate_verdict,
    assertion_agreement,
    assertion_pass_rates,
    build_report,
    calibration_gate,
    coverage_stability,
    escalation_summary,
    failure_mode_pass_rates,
    format_conversation,
    get_source_trace,
    load_golden_records,
    load_source_records,
    message_text,
    next_rerun_id,
    print_summary,
    record_agreement,
    replay_blocker,
    rubric_pass_rates,
    should_escalate,
    to_state,
    to_turn_plan,
    to_verdict,
    unannotated_ids,
    validate_human_verdicts,
    wilson_interval,
)
from evals.rubric import FAILURE_MODE_SCOPE, RUBRIC_SCOPE
from graph.llm import llm_judge


def outcome(
    assertion_id: str = "a1",
    *,
    polarity: str = "must",
    verdict: str = "pass",
    human: str = "",
    assertion_type: str = "judge",
    decided_by: str = "check",
    screen_holds: bool | None = None,
    screen_detail: str = "",
    scope: str = FAILURE_MODE_SCOPE,
) -> AssertionOutcome:
    return AssertionOutcome(
        assertion_id=assertion_id,
        assertion_type=assertion_type,
        polarity=polarity,
        holds=None,
        verdict=verdict,
        human_verdict=human,
        detail="",
        decided_by=decided_by,
        screen_holds=screen_holds,
        screen_detail=screen_detail,
        scope=scope,
    )


def instance(failure_mode: str, trace_id: str, human_pass: bool | None, runs: list[RunResult]) -> InstanceResult:
    return InstanceResult(failure_mode=failure_mode, source_trace_id=trace_id, human_pass=human_pass, runs=runs)


class TestToVerdict:
    def test_must_maps_holds_to_pass(self) -> None:
        assert to_verdict("must", True) == "pass"
        assert to_verdict("must", False) == "fail"

    def test_must_not_inverts(self) -> None:
        assert to_verdict("must_not", True) == "fail"
        assert to_verdict("must_not", False) == "pass"

    def test_unknown_polarity_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown polarity"):
            to_verdict("should", True)


class TestShouldEscalate:
    def test_must_escalates_when_holds_false(self) -> None:
        assert should_escalate("must", False) is True
        assert should_escalate("must", True) is False

    def test_must_not_escalates_when_holds_true(self) -> None:
        assert should_escalate("must_not", True) is True
        assert should_escalate("must_not", False) is False


class TestWilsonInterval:
    def test_no_samples_yields_none(self) -> None:
        assert wilson_interval(0, 0) is None

    def test_18_of_20(self) -> None:
        lower, upper = wilson_interval(18, 20)  # type: ignore[misc]
        assert lower == pytest.approx(0.699, abs=0.01)
        assert upper == pytest.approx(0.972, abs=0.01)

    def test_all_pass_upper_bound_caps_at_one(self) -> None:
        lower, upper = wilson_interval(20, 20)  # type: ignore[misc]
        assert upper == pytest.approx(1.0)
        assert lower == pytest.approx(0.839, abs=0.01)


class TestAggregateVerdict:
    def test_all_pass(self) -> None:
        assert aggregate_verdict([outcome("a1"), outcome("a2", polarity="must_not")]) == "pass"

    def test_single_fail_fails_the_record(self) -> None:
        assert aggregate_verdict([outcome("a1"), outcome("a2", verdict="fail")]) == "fail"

    def test_na_is_neutral(self) -> None:
        assert aggregate_verdict([outcome("a1"), outcome("a2", verdict="na")]) == "pass"

    def test_all_na_passes(self) -> None:
        assert aggregate_verdict([outcome("a1", verdict="na")]) == "pass"


class TestAssertionOutcomeFlags:
    def test_na_is_not_applicable_and_never_agrees(self) -> None:
        na = outcome(verdict="na", human="na")
        assert not na.applicable
        assert not na.agrees

    def test_missing_human_label_never_agrees(self) -> None:
        assert not outcome(verdict="pass", human="").agrees

    def test_matching_labels_agree(self) -> None:
        assert outcome(verdict="pass", human="pass").agrees


class TestAssertionAgreement:
    def test_confusion_matrix_treats_human_fail_as_positive(self) -> None:
        runs = [
            RunResult(
                run_index=1,
                output="",
                outcomes=[
                    outcome("a1", verdict="fail", human="fail"),  # TP
                    outcome("a2", verdict="pass", human="pass"),  # TN
                    outcome("a3", verdict="fail", human="pass"),  # FP
                    outcome("a4", verdict="pass", human="fail"),  # FN
                ],
            )
        ]
        result = assertion_agreement([instance("fm", "t1", False, runs)])

        assert result["confusion_matrix"] == {"tp": 1, "tn": 1, "fp": 1, "fn": 1}
        assert result["total"] == 4
        assert result["agreed"] == 2
        assert result["agreement_rate"] == 0.5
        assert result["tpr"] == 0.5
        assert result["tnr"] == 0.5

    def test_na_is_excluded_from_the_denominator_but_counted(self) -> None:
        runs = [
            RunResult(
                run_index=1,
                output="",
                outcomes=[outcome("a1", verdict="pass", human="pass"), outcome("a2", verdict="na", human="na")],
            )
        ]
        result = assertion_agreement([instance("fm", "t1", True, runs)])

        assert result["total"] == 1
        assert result["not_applicable"] == 1

    def test_mismatches_list_names_the_assertion(self) -> None:
        runs = [RunResult(run_index=1, output="", outcomes=[outcome("a2", verdict="fail", human="pass")])]
        result = assertion_agreement([instance("fm", "t1", True, runs)])

        assert [m["assertion_id"] for m in result["mismatches"]] == ["a2"]

    def test_empty_input_yields_no_rate(self) -> None:
        assert assertion_agreement([])["agreement_rate"] is None


class TestAssertionOutcomeCascade:
    def test_non_escalated_screen_verdict_matches_final(self) -> None:
        o = outcome(polarity="must_not", verdict="pass", decided_by="screen", screen_holds=False)
        assert o.screen_verdict == "pass"
        assert o.escalated is False

    def test_escalated_screen_verdict_keeps_screen_fail(self) -> None:
        # screen said holds=True (must_not -> fail), confirm overturned to pass.
        o = outcome(polarity="must_not", verdict="pass", decided_by="confirm", screen_holds=True)
        assert o.screen_verdict == "fail"
        assert o.verdict == "pass"
        assert o.escalated is True

    def test_deterministic_screen_verdict_falls_back_to_final(self) -> None:
        o = outcome(assertion_type="deterministic", verdict="pass", decided_by="check", screen_holds=None)
        assert o.screen_verdict == "pass"

    def test_na_screen_verdict_falls_back_to_final(self) -> None:
        o = outcome(verdict="na", decided_by="na", screen_holds=None)
        assert o.screen_verdict == "na"


class TestAssertionAgreementStage:
    def _escalated_overturned(self) -> RunResult:
        # screen said fail (FP against a positive), confirm overturned to pass (TN).
        return RunResult(
            run_index=1,
            output="",
            outcomes=[
                outcome(
                    "a2", polarity="must_not", verdict="pass", human="pass", decided_by="confirm", screen_holds=True
                )
            ],
        )

    def test_screen_stage_counts_the_overturned_fp(self) -> None:
        result = assertion_agreement([instance("fm", "t1", True, [self._escalated_overturned()])], stage="screen")
        assert result["confusion_matrix"] == {"tp": 0, "tn": 0, "fp": 1, "fn": 0}

    def test_final_stage_counts_the_confirmed_tn(self) -> None:
        result = assertion_agreement([instance("fm", "t1", True, [self._escalated_overturned()])], stage="final")
        assert result["confusion_matrix"] == {"tp": 0, "tn": 1, "fp": 0, "fn": 0}

    def test_default_stage_is_final(self) -> None:
        runs = [self._escalated_overturned()]
        assert assertion_agreement([instance("fm", "t1", True, runs)]) == assertion_agreement(
            [instance("fm", "t1", True, runs)], stage="final"
        )


class TestEscalationSummary:
    def test_counts_escalated_and_overturned(self) -> None:
        overturned = outcome(
            "a2", polarity="must_not", verdict="pass", human="pass", decided_by="confirm", screen_holds=True
        )
        confirmed_fail = outcome(
            "a3", polarity="must_not", verdict="fail", human="fail", decided_by="confirm", screen_holds=True
        )
        not_escalated = outcome("a1", polarity="must", verdict="pass", human="pass", decided_by="screen")
        run = RunResult(run_index=1, output="", outcomes=[overturned, confirmed_fail, not_escalated])
        summary = escalation_summary([instance("fm", "t1", True, [run])])

        assert summary["total_judge"] == 3
        assert summary["escalated"] == 2
        assert summary["confirmed_fail"] == 1
        assert summary["overturned_to_pass"] == 1
        assert [o["assertion_id"] for o in summary["overturned"]] == ["a2"]

    def test_na_and_deterministic_are_excluded_from_total_judge(self) -> None:
        na = outcome("a4", verdict="na", decided_by="na")
        deterministic = outcome("a5", assertion_type="deterministic", verdict="pass", decided_by="check")
        run = RunResult(run_index=1, output="", outcomes=[na, deterministic])
        summary = escalation_summary([instance("fm", "t1", True, [run])])

        assert summary["total_judge"] == 0
        assert summary["escalated"] == 0


class TestCalibrationGate:
    def _results(
        self, *, tp: int, tn: int, fp: int, fn: int, positive_extra_fail: bool = False
    ) -> list[InstanceResult]:
        outcomes = (
            [outcome("a1", verdict="fail", human="fail") for _ in range(tp)]
            + [outcome("a1", verdict="pass", human="pass") for _ in range(tn)]
            + [outcome("a1", verdict="fail", human="pass") for _ in range(fp)]
            + [outcome("a1", verdict="pass", human="fail") for _ in range(fn)]
        )
        # human_pass=False here so these synthetic instances never trip the positive-record
        # check below — they exist only to populate the assertion-level confusion matrix.
        results = [instance(f"fm{i}", f"t{i}", False, [RunResult(1, "", [o])]) for i, o in enumerate(outcomes)]
        if positive_extra_fail:
            failing_run = RunResult(1, "", [outcome("a1", verdict="fail", human="")])
            results.append(instance("fm-extra", "t-extra-positive", True, [failing_run]))
        return results

    def test_passes_when_all_thresholds_met(self) -> None:
        gate = calibration_gate(self._results(tp=9, tn=9, fp=0, fn=0), stage="final")
        assert gate["passed"] is True
        assert gate["failures"] == []

    def test_fails_below_tnr_threshold(self) -> None:
        gate = calibration_gate(self._results(tp=9, tn=8, fp=2, fn=0), stage="final")
        assert gate["passed"] is False
        assert any("TNR" in reason for reason in gate["failures"])

    def test_screen_stage_names_the_cascade_limitation_on_low_tpr(self) -> None:
        gate = calibration_gate(self._results(tp=8, tn=9, fp=0, fn=2), stage="screen")
        assert gate["passed"] is False
        assert any("カスケードで救えない" in reason for reason in gate["failures"])

    def test_screen_stage_low_tnr_omits_the_cascade_caveat(self) -> None:
        gate = calibration_gate(self._results(tp=9, tn=8, fp=2, fn=0), stage="screen")
        assert gate["passed"] is False
        assert [reason for reason in gate["failures"] if "screen" in reason] == []

    def test_final_stage_omits_screen_notes(self) -> None:
        gate = calibration_gate(self._results(tp=8, tn=8, fp=2, fn=2), stage="final")
        assert gate["passed"] is False
        assert [reason for reason in gate["failures"] if "screen" in reason] == []

    def test_final_stage_requires_all_positive_records_to_pass(self) -> None:
        gate = calibration_gate(self._results(tp=9, tn=9, fp=0, fn=0, positive_extra_fail=True), stage="final")
        assert gate["passed"] is False
        assert gate["positive_records"]["total"] == 1
        assert gate["positive_records"]["passed"] == 0

    def test_no_samples_reports_missing_class(self) -> None:
        gate = calibration_gate([], stage="final")
        assert gate["passed"] is False
        assert gate["tpr"] is None
        assert gate["tnr"] is None


class TestRecordAgreement:
    def test_compares_aggregated_verdict_with_instance_pass(self) -> None:
        passing = RunResult(run_index=1, output="", outcomes=[outcome("a1", verdict="pass")])
        failing = RunResult(run_index=1, output="", outcomes=[outcome("a1", verdict="fail")])
        results = [
            instance("fm", "positive", True, [passing]),
            instance("fm", "negative", False, [failing]),
            instance("fm", "mislabeled", True, [failing]),
        ]
        result = record_agreement(results)

        assert result["total"] == 3
        assert result["agreed"] == 2
        assert [m["source_trace_id"] for m in result["mismatches"]] == ["mislabeled"]

    def test_instances_without_human_label_are_skipped(self) -> None:
        runs = [RunResult(run_index=1, output="", outcomes=[outcome("a1")])]
        assert record_agreement([instance("fm", "t1", None, runs)])["total"] == 0


class TestPassRates:
    def test_assertion_pass_rate_counts_runs_and_excludes_na(self) -> None:
        results = [
            instance(
                "fm",
                "t1",
                False,
                [
                    RunResult(1, "", [outcome("a1", verdict="pass"), outcome("a2", verdict="na")]),
                    RunResult(2, "", [outcome("a1", verdict="fail"), outcome("a2", verdict="na")]),
                ],
            )
        ]
        rates = {row["assertion_id"]: row for row in assertion_pass_rates(results)}

        assert rates["a1"]["runs"] == 2
        assert rates["a1"]["passed"] == 1
        assert rates["a1"]["pass_rate"] == 0.5
        assert rates["a2"]["not_applicable"] == 2
        assert rates["a2"]["pass_rate"] is None

    def test_failure_mode_pass_rate_aggregates_runs(self) -> None:
        results = [
            instance("fm", "t1", False, [RunResult(1, "", [outcome("a1", verdict="pass")])]),
            instance("fm", "t2", False, [RunResult(1, "", [outcome("a1", verdict="fail")])]),
        ]
        assert failure_mode_pass_rates(results) == [{"failure_mode": "fm", "runs": 2, "passed": 1, "pass_rate": 0.5}]


class TestRunResultVerdict:
    def test_uses_aggregate_verdict(self) -> None:
        run = RunResult(1, "", [outcome("a1", verdict="pass"), outcome("a2", verdict="fail")])
        assert run.verdict == "fail"

    def test_generation_is_optional(self) -> None:
        run = RunResult(1, "out", [outcome("a1")], Generation("out", None, [], 3))
        assert run.generation is not None
        assert run.generation.turn_count == 3


class TestNextRerunId:
    def test_starts_at_one(self) -> None:
        assert next_rerun_id("t1", set()) == "t1-rerun01"

    def test_skips_taken_indexes_so_sessions_accumulate(self) -> None:
        assert next_rerun_id("t1", {"t1-rerun01", "t1-rerun02"}) == "t1-rerun03"

    def test_other_traces_do_not_shift_the_index(self) -> None:
        assert next_rerun_id("t1", {"t2-rerun01"}) == "t1-rerun01"


class TestMessageText:
    def test_plain_string_content(self) -> None:
        assert message_text(AIMessage(content="こんにちは")) == "こんにちは"

    def test_block_content_is_concatenated(self) -> None:
        message = AIMessage(content=[{"type": "text", "text": "前半"}, {"type": "text", "text": "後半"}])
        assert message_text(message) == "前半後半"

    def test_non_text_blocks_contribute_nothing(self) -> None:
        assert message_text(AIMessage(content=[{"type": "image_url", "image_url": {"url": "x"}}])) == ""


def test_format_conversation_labels_each_turn() -> None:
    history = [{"role": "assistant", "content": "問いかけ"}, {"role": "user", "content": "回答"}]
    assert format_conversation(history) == "assistant: 問いかけ\nuser: 回答"


class TestToState:
    def _trace(self, graph_state: dict[str, object]) -> SourceTrace:
        return SourceTrace(
            trace_id="t1",
            turn=3,
            meta={},
            input={
                "conversation_history": [
                    {"role": "assistant", "content": "問いかけ"},
                    {"role": "user", "content": "回答"},
                ],
                "graph_state": {"topic": "プロセス", **graph_state},
            },
            observed_output="",
        )

    def test_roles_map_to_message_types(self) -> None:
        state = to_state(self._trace({}))
        assert [type(m) for m in state["messages"]] == [AIMessage, HumanMessage]
        assert state["topic"] == "プロセス"
        assert state["turn_count"] == 3
        assert state["session_type"] == "learning"

    def test_empty_optional_fields_are_left_unset(self) -> None:
        state = to_state(self._trace({"learning_goal": None, "focus_aspects": []}))
        assert "learning_goal" not in state
        assert "focus_aspects" not in state
        assert "covered_aspects" not in state

    def test_present_optional_fields_are_carried_over(self) -> None:
        state = to_state(self._trace({"learning_goal": "理解する", "focus_aspects": ["定義"]}))
        assert state["learning_goal"] == "理解する"
        assert state["focus_aspects"] == ["定義"]

    def test_record_captured_before_wrap_up_suppresses_it(self) -> None:
        state = to_state(self._trace({}))
        assert state["wrap_up_offered"] is True

    def test_captured_wrap_up_flag_is_carried_over(self) -> None:
        state = to_state(self._trace({"wrap_up_offered": False}))
        assert state["wrap_up_offered"] is False


class TestSourceRecords:
    def test_every_record_is_keyed_by_id(self) -> None:
        sources = load_source_records()
        assert sources
        assert all(record["id"] == trace_id for trace_id, record in sources.items())

    def test_get_source_trace_reads_the_canonical_fields(self) -> None:
        sources = load_source_records()
        trace_id = "2026-07-14-os-process__t1"
        trace = get_source_trace(trace_id, sources)

        assert trace.trace_id == trace_id
        assert trace.observed_output == sources[trace_id]["output"]
        assert trace.input == sources[trace_id]["input"]

    def test_unknown_trace_id_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown source_trace_id"):
            get_source_trace("nope", {})


def golden(*, assertion_ids: list[str], human_verdicts: dict[str, str]) -> dict[str, Any]:
    return {
        "failure_mode": "fm",
        "assertions": [{"id": assertion_id} for assertion_id in assertion_ids],
        "instances": [{"source_trace_id": "t1", "human_verdicts": human_verdicts}],
    }


class TestValidateHumanVerdicts:
    def test_accepts_exact_key_match(self) -> None:
        validate_human_verdicts([golden(assertion_ids=["a1", "a2"], human_verdicts={"a1": "pass", "a2": "na"})])

    def test_missing_label_raises(self) -> None:
        with pytest.raises(ValueError, match="ラベルが無い assertion: a2"):
            validate_human_verdicts([golden(assertion_ids=["a1", "a2"], human_verdicts={"a1": "pass"})])

    def test_label_for_undeclared_assertion_raises(self) -> None:
        with pytest.raises(ValueError, match="assertions に無い id へのラベル: a9"):
            validate_human_verdicts([golden(assertion_ids=["a1"], human_verdicts={"a1": "pass", "a9": "fail"})])

    def test_unknown_verdict_value_raises(self) -> None:
        with pytest.raises(ValueError, match="不正な verdict 'Fail'"):
            validate_human_verdicts([golden(assertion_ids=["a1"], human_verdicts={"a1": "Fail"})])

    def test_reports_every_problem_at_once(self) -> None:
        with pytest.raises(ValueError) as exc:
            validate_human_verdicts([golden(assertion_ids=["a1", "a2"], human_verdicts={"a1": "yes", "a9": "pass"})])

        message = str(exc.value)
        assert "ラベルが無い assertion: a2" in message
        assert "assertions に無い id へのラベル: a9" in message
        assert "不正な verdict 'yes'" in message

    def test_active_golden_corpus_is_valid(self) -> None:
        records = list(load_golden_records())
        assert records
        validate_human_verdicts(records)


def _trace(meta: dict[str, Any]) -> SourceTrace:
    return SourceTrace(trace_id="t", turn=4, meta=meta, input={"graph_state": {"topic": "x"}}, observed_output="o")


def test_replay_blocker_passes_capture_derived_records() -> None:
    assert replay_blocker(_trace({"captured_by": "capture"})) is None


def test_replay_blocker_rejects_hand_written_records() -> None:
    blocker = replay_blocker(_trace({"model": "gpt-4.1"}))

    assert blocker is not None
    assert "capture" in blocker


def test_replay_blocker_rejects_map_route_records_in_every_mode() -> None:
    meta = {"captured_by": "capture", "route": "map"}

    assert "地図" in (replay_blocker(_trace(meta), "full") or "")
    assert "地図" in (replay_blocker(_trace(meta), "pinned") or "")


def test_unannotated_ids_lists_records_without_a_human_label() -> None:
    sources: dict[str, dict[str, Any]] = {
        "a": {"id": "a", "pass": None},
        "b": {"id": "b", "pass": False},
        "c": {"id": "c", "pass": True},
    }

    assert unannotated_ids(sources) == ["a"]


def test_replay_blocker_rejects_pinned_replay_without_a_decision() -> None:
    trace = _trace({"captured_by": "capture"})

    assert replay_blocker(trace, "full") is None
    assert "turn_decision" in (replay_blocker(trace, "pinned") or "")


def test_to_turn_plan_restores_the_saved_decision() -> None:
    covered = [{"aspect": "スループット", "reached_depth": "defined"}]
    trace = SourceTrace(
        trace_id="t",
        turn=4,
        meta={},
        input={"graph_state": {"topic": "x", "covered_aspects": []}},
        observed_output="o",
        turn_decision={
            "response_mode": "expand",
            "selected_aspect": "スループット",
            "error_summary": "",
            "covered_aspects": covered,
        },
        has_turn_decision=True,
    )

    plan = to_turn_plan(trace)

    assert plan.covered_aspects == covered
    assert plan.analysis is not None
    assert plan.analysis.response_mode == "expand"
    assert plan.analysis.selected_aspect == "スループット"
    assert plan.analysis.observations == []
    # 誤り判定を足す前に capture したレコードにはこのキーが無い。落とさず未検出として再生する
    assert plan.analysis.has_misconception is False
    assert plan.wrap_up is False


def test_to_turn_plan_restores_a_wrap_up_decision() -> None:
    trace = SourceTrace(
        trace_id="t",
        turn=8,
        meta={},
        input={"graph_state": {"topic": "x", "covered_aspects": []}},
        observed_output="o",
        turn_decision={
            "response_mode": "expand",
            "selected_aspect": "スループット",
            "has_misconception": False,
            "error_summary": "",
            "wrap_up": True,
            "covered_aspects": [],
        },
        has_turn_decision=True,
    )

    assert to_turn_plan(trace).wrap_up is True


def test_to_turn_plan_restores_a_flagged_misconception() -> None:
    trace = SourceTrace(
        trace_id="t",
        turn=4,
        meta={},
        input={"graph_state": {"topic": "x", "covered_aspects": []}},
        observed_output="o",
        turn_decision={
            "response_mode": "reinforce",
            "selected_aspect": "プロセスの管理",
            "has_misconception": True,
            "error_summary": "並行処理を仕組みそのものとして述べている",
            "covered_aspects": [],
        },
        has_turn_decision=True,
    )

    plan = to_turn_plan(trace)

    assert plan.analysis is not None
    assert plan.analysis.has_misconception is True
    assert plan.analysis.error_summary == "並行処理を仕組みそのものとして述べている"


def test_to_turn_plan_falls_back_to_the_input_coverage_when_no_analysis_ran() -> None:
    covered = [{"aspect": "定義", "reached_depth": "mentioned"}]
    trace = SourceTrace(
        trace_id="t",
        turn=4,
        meta={},
        input={"graph_state": {"topic": "x", "covered_aspects": covered}},
        observed_output="o",
        turn_decision=None,
        has_turn_decision=True,
    )

    plan = to_turn_plan(trace)

    assert plan.analysis is None
    assert plan.covered_aspects == covered


def _run_with_coverage(aspects: list[list[str]]) -> InstanceResult:
    result = InstanceResult(failure_mode="fm", source_trace_id="t", human_pass=None)
    for index, names in enumerate(aspects, start=1):
        generation = Generation(
            output="o",
            turn_analysis={"response_mode": "expand", "selected_aspect": names[0], "error_summary": ""},
            covered_aspects=[{"aspect": name, "reached_depth": "defined"} for name in names],
            turn_count=2,
        )
        result.runs.append(RunResult(run_index=index, output="o", outcomes=[], generation=generation))
    return result


def test_coverage_stability_is_one_when_every_run_names_the_same_aspects() -> None:
    rows = coverage_stability([_run_with_coverage([["定義"], ["定義"]])])

    assert rows[0]["mean_jaccard"] == 1.0


def test_coverage_stability_detects_a_drifting_aspect_vocabulary() -> None:
    rows = coverage_stability([_run_with_coverage([["定義"], ["メモリ空間", "独立性", "実行単位"]])])

    assert rows[0]["mean_jaccard"] == 0.0
    assert rows[0]["aspect_sets"] == [["定義"], ["メモリ空間", "実行単位", "独立性"]]


def test_coverage_stability_skips_single_run_instances() -> None:
    assert coverage_stability([_run_with_coverage([["定義"]])]) == []


def test_report_preserves_per_run_coverage_for_pinned_replay() -> None:
    result = _run_with_coverage([["定義"], ["具体例"]])
    report = build_report([result], [], mode="regression", runs=2, fingerprints={}, judge=llm_judge)
    runs = report["records"][0]["runs"]
    for index, name in enumerate(("定義", "具体例")):
        assert runs[index]["covered_aspects"] == [{"aspect": name, "reached_depth": "defined"}]
        trace = SourceTrace(
            trace_id="replay",
            turn=1,
            meta={},
            input={},
            observed_output="",
            turn_decision={**runs[index]["turn_analysis"], "covered_aspects": runs[index]["covered_aspects"]},
            has_turn_decision=True,
        )
        assert to_turn_plan(trace).covered_aspects == runs[index]["covered_aspects"]


@pytest.mark.parametrize("mode", ["scoring", "regression"])
def test_print_summary_runs_for_both_modes(mode: str, capsys: pytest.CaptureFixture[str]) -> None:
    """レポート組み立てと表示の経路を通す（判定は他のテスト、ここは KeyError 等の検出）。"""
    report = build_report(
        [],
        errors=["boom"],
        mode=mode,
        runs=3,
        fingerprints={},
        judge=llm_judge,
        skipped=[{"failure_mode": "fm", "source_trace_id": "t", "reason": "r"}],
        replay_mode="pinned",
    )

    print_summary(report)

    out = capsys.readouterr().out
    assert "boom" in out
    assert report["meta"]["mode"] == mode


class TestRubricPassRates:
    def test_rubric_assertions_are_pooled_across_failure_modes(self) -> None:
        results = [
            instance(
                "accurate_multi_concept_overexplain",
                "t1",
                False,
                [RunResult(0, "out", [outcome("a1"), outcome("r2", verdict="fail", scope=RUBRIC_SCOPE)])],
            ),
            instance(
                "self_answered_question",
                "t2",
                True,
                [RunResult(0, "out", [outcome("a1"), outcome("r2", scope=RUBRIC_SCOPE)])],
            ),
        ]

        rates = rubric_pass_rates(results)

        assert [r["assertion_id"] for r in rates] == ["r2"]
        assert rates[0] == {
            "assertion_id": "r2",
            "runs": 2,
            "not_applicable": 0,
            "passed": 1,
            "pass_rate": 0.5,
        }

    def test_not_applicable_leaves_the_denominator(self) -> None:
        results = [
            instance(
                "self_answered_question",
                "t1",
                False,
                [RunResult(0, "out", [outcome("r1", verdict="na", scope=RUBRIC_SCOPE)])],
            )
        ]

        rates = rubric_pass_rates(results)

        assert rates[0]["not_applicable"] == 1
        assert rates[0]["pass_rate"] is None

    def test_failure_mode_assertions_are_excluded(self) -> None:
        results = [instance("self_answered_question", "t1", False, [RunResult(0, "out", [outcome("a1")])])]

        assert rubric_pass_rates(results) == []

    def test_per_assertion_rates_carry_the_scope(self) -> None:
        results = [
            instance(
                "self_answered_question",
                "t1",
                False,
                [RunResult(0, "out", [outcome("a1"), outcome("r1", scope=RUBRIC_SCOPE)])],
            )
        ]

        scopes = {r["assertion_id"]: r["scope"] for r in assertion_pass_rates(results)}

        assert scopes == {"a1": FAILURE_MODE_SCOPE, "r1": RUBRIC_SCOPE}
