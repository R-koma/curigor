import math
from typing import Any

from evals.dataset import NOT_APPLICABLE
from evals.replay import Generation
from evals.rubric import RUBRIC_SCOPE
from evals.runner import AssertionOutcome, InstanceResult


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    """二項比率の Wilson score 95%（既定）信頼区間。標本が無ければ None。"""
    if total == 0:
        return None
    phat = successes / total
    denom = 1 + z**2 / total
    center = phat + z**2 / (2 * total)
    margin = z * math.sqrt(phat * (1 - phat) / total + z**2 / (4 * total**2))
    lower = (center - margin) / denom
    upper = (center + margin) / denom
    return max(0.0, lower), min(1.0, upper)


def assertion_pass_rates(results: list[InstanceResult]) -> list[dict[str, Any]]:
    rates: list[dict[str, Any]] = []
    for result in results:
        by_assertion: dict[str, list[str]] = {}
        scopes: dict[str, str] = {}
        for run in result.runs:
            for outcome in run.outcomes:
                by_assertion.setdefault(outcome.assertion_id, []).append(outcome.verdict)
                scopes[outcome.assertion_id] = outcome.scope
        for assertion_id, verdicts in by_assertion.items():
            scored = [v for v in verdicts if v != NOT_APPLICABLE]
            rates.append(
                {
                    "failure_mode": result.failure_mode,
                    "source_trace_id": result.source_trace_id,
                    "assertion_id": assertion_id,
                    "scope": scopes[assertion_id],
                    "runs": len(verdicts),
                    "not_applicable": len(verdicts) - len(scored),
                    "passed": sum(1 for v in scored if v == "pass"),
                    "pass_rate": (sum(1 for v in scored if v == "pass") / len(scored)) if scored else None,
                }
            )
    return rates


def rubric_pass_rates(results: list[InstanceResult]) -> list[dict[str, Any]]:
    """共通 assertion の pass 率。failure_mode をまたぐので instance 単位では束ねない。"""
    by_assertion: dict[str, list[str]] = {}
    for result in results:
        for run in result.runs:
            for outcome in run.outcomes:
                if outcome.scope == RUBRIC_SCOPE:
                    by_assertion.setdefault(outcome.assertion_id, []).append(outcome.verdict)
    rates: list[dict[str, Any]] = []
    for assertion_id, verdicts in sorted(by_assertion.items()):
        scored = [v for v in verdicts if v != NOT_APPLICABLE]
        rates.append(
            {
                "assertion_id": assertion_id,
                "runs": len(verdicts),
                "not_applicable": len(verdicts) - len(scored),
                "passed": sum(1 for v in scored if v == "pass"),
                "pass_rate": (sum(1 for v in scored if v == "pass") / len(scored)) if scored else None,
            }
        )
    return rates


def failure_mode_pass_rates(results: list[InstanceResult]) -> list[dict[str, Any]]:
    by_mode: dict[str, list[str]] = {}
    for result in results:
        for run in result.runs:
            by_mode.setdefault(result.failure_mode, []).append(run.verdict)
    return [
        {
            "failure_mode": mode,
            "runs": len(verdicts),
            "passed": sum(1 for v in verdicts if v == "pass"),
            "pass_rate": sum(1 for v in verdicts if v == "pass") / len(verdicts),
        }
        for mode, verdicts in sorted(by_mode.items())
    ]


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def _coverage_ids(generation: Generation) -> set[str]:
    if generation.depth_map is not None:
        return {c["aspect_id"] for c in generation.map_covered}
    return {a["aspect"] for a in generation.covered_aspects}


def coverage_stability(results: list[InstanceResult]) -> list[dict[str, Any]]:
    """同一入力の run 間で、事前分析が付ける観点名がどれだけ一致するかを測る。

    `merge_coverage` は観点名の文字列をキーに dedup するため、run ごとに粒度が変われば
    多ターンで「既出観点を再質問しない」が静かに壊れる。その揺れを数字にする。
    """
    rows: list[dict[str, Any]] = []
    for result in results:
        aspect_sets = [_coverage_ids(run.generation) for run in result.runs if run.generation is not None]
        if len(aspect_sets) < 2:
            continue
        pairs = [
            _jaccard(aspect_sets[i], aspect_sets[j])
            for i in range(len(aspect_sets))
            for j in range(i + 1, len(aspect_sets))
        ]
        rows.append(
            {
                "failure_mode": result.failure_mode,
                "source_trace_id": result.source_trace_id,
                "runs": len(aspect_sets),
                "mean_jaccard": sum(pairs) / len(pairs),
                "aspect_sets": [sorted(s) for s in aspect_sets],
            }
        )
    return rows


def assertion_agreement(results: list[InstanceResult], *, stage: str = "final") -> dict[str, Any]:
    """judge–人間一致を混同行列で出す。`stage="screen"` はカスケードの screen 単体を見る。

    stage="screen" で applicable / human_verdict の判定は screen ではなく final の値を使う
    （na は applies_when という input の性質で、カスケードの有無に関わらず同じ扱いになるため）。
    """

    def verdict_of(o: AssertionOutcome) -> str:
        return o.screen_verdict if stage == "screen" else o.verdict

    outcomes = [o for r in results for run in r.runs for o in run.outcomes]
    scored = [o for o in outcomes if o.applicable and o.human_verdict]
    tp = sum(1 for o in scored if o.human_verdict == "fail" and verdict_of(o) == "fail")
    fn = sum(1 for o in scored if o.human_verdict == "fail" and verdict_of(o) == "pass")
    fp = sum(1 for o in scored if o.human_verdict == "pass" and verdict_of(o) == "fail")
    tn = sum(1 for o in scored if o.human_verdict == "pass" and verdict_of(o) == "pass")
    total = len(scored)
    return {
        "granularity": "assertion",
        "stage": stage,
        "total": total,
        "agreed": tp + tn,
        "agreement_rate": (tp + tn) / total if total else None,
        "not_applicable": sum(1 for o in outcomes if not o.applicable),
        "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "tpr": tp / (tp + fn) if tp + fn else None,
        "tnr": tn / (tn + fp) if tn + fp else None,
        "mismatches": [
            {
                "failure_mode": r.failure_mode,
                "source_trace_id": r.source_trace_id,
                "assertion_id": o.assertion_id,
                "judged": verdict_of(o),
                "human": o.human_verdict,
                "detail": o.screen_detail if stage == "screen" and o.assertion_type == "judge" else o.detail,
            }
            for r in results
            for run in r.runs
            for o in run.outcomes
            if o.applicable and o.human_verdict and verdict_of(o) != o.human_verdict
        ],
    }


def escalation_summary(results: list[InstanceResult]) -> dict[str, Any]:
    """カスケードで screen から confirm に回った judge assertion の内訳。

    overturned（screen=fail → confirm=pass）は Haiku と Opus が割れた箇所そのもので、
    criterion レビューの入力になる（README.md の規約: 割れたら criterion の曖昧さを疑う）。
    """
    judged = [
        (r, o) for r in results for run in r.runs for o in run.outcomes if o.assertion_type == "judge" and o.applicable
    ]
    escalated = [(r, o) for r, o in judged if o.escalated]
    confirmed_fail = [o for _, o in escalated if o.verdict == "fail"]
    overturned = [o for _, o in escalated if o.verdict == "pass"]
    return {
        "total_judge": len(judged),
        "escalated": len(escalated),
        "confirmed_fail": len(confirmed_fail),
        "overturned_to_pass": len(overturned),
        "overturned": [
            {
                "failure_mode": r.failure_mode,
                "source_trace_id": r.source_trace_id,
                "assertion_id": o.assertion_id,
                "screen_detail": o.screen_detail,
                "confirm_detail": o.detail,
            }
            for r, o in escalated
            if o.verdict == "pass"
        ],
    }


def record_agreement(results: list[InstanceResult]) -> dict[str, Any]:
    """instance 全体の pass/fail を人間ラベル（instance["pass"]）と突き合わせる。"""
    pairs = [
        (run.verdict, "pass" if r.human_pass else "fail")
        for r in results
        if r.human_pass is not None
        for run in r.runs
    ]
    agreed = sum(1 for judged, human in pairs if judged == human)
    return {
        "granularity": "record",
        "total": len(pairs),
        "agreed": agreed,
        "agreement_rate": agreed / len(pairs) if pairs else None,
        "mismatches": [
            {
                "failure_mode": r.failure_mode,
                "source_trace_id": r.source_trace_id,
                "judged": run.verdict,
                "human": "pass" if r.human_pass else "fail",
            }
            for r in results
            if r.human_pass is not None
            for run in r.runs
            if run.verdict != ("pass" if r.human_pass else "fail")
        ],
    }


def assertion_agreement_rates(results: list[InstanceResult]) -> list[dict[str, Any]]:
    """assertion ごとに instance を跨いで judge–人間一致を集計する。

    pass 率は負例と正例で目標値が逆になり、コーパスの構成を知らないと読めない。
    scoring で見るべきは「judge がラベルと合っているか」なので、目標が常に 100% の指標にする。
    """
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for result in results:
        for run in result.runs:
            for outcome in run.outcomes:
                if not outcome.applicable or not outcome.human_verdict:
                    continue
                key = (result.failure_mode, outcome.assertion_id)
                row = rows.setdefault(
                    key,
                    {"failure_mode": key[0], "assertion_id": key[1], "total": 0, "agreed": 0, "mismatches": []},
                )
                row["total"] += 1
                if outcome.agrees:
                    row["agreed"] += 1
                else:
                    row["mismatches"].append(
                        {
                            "source_trace_id": result.source_trace_id,
                            "judged": outcome.verdict,
                            "human": outcome.human_verdict,
                        }
                    )
    return [rows[key] for key in sorted(rows)]


def calibration_gate(
    results: list[InstanceResult], *, stage: str, tpr_min: float = 0.9, tnr_min: float = 0.9
) -> dict[str, Any]:
    """方向別の合格条件（TPR ≥ tpr_min かつ TNR ≥ tnr_min）で judge を評価する。

    総合一致率だけでは「良いものを fail と言う」偏り（P1）が 90% の下に隠れるため、
    TPR/TNR を別々にゲートする。`stage="final"` のときだけ正例レコードが judge 集約で
    全件 pass になることも要求する（record_agreement とは独立に、この gate 自体で判定する）。
    """
    agreement = assertion_agreement(results, stage=stage)
    matrix = agreement["confusion_matrix"]
    tp, tn, fp, fn = matrix["tp"], matrix["tn"], matrix["fp"], matrix["fn"]
    tpr, tnr = agreement["tpr"], agreement["tnr"]
    tpr_ci = wilson_interval(tp, tp + fn)
    tnr_ci = wilson_interval(tn, tn + fp)

    failures: list[str] = []
    if tpr is None:
        failures.append("TPR: 陽性（人間ラベル fail）の標本が無い")
    elif tpr < tpr_min:
        failures.append(f"TPR {tpr:.0%} が閾値 {tpr_min:.0%} 未満")
        if stage == "screen":
            failures.append("screen の FN はカスケードで救えない（confirm は screen=fail のときだけ動く）")
    if tnr is None:
        failures.append("TNR: 陰性（人間ラベル pass）の標本が無い")
    elif tnr < tnr_min:
        failures.append(f"TNR {tnr:.0%} が閾値 {tnr_min:.0%} 未満")

    positive_records = {"total": 0, "passed": 0}
    if stage == "final":
        positives = [r for r in results if r.human_pass is True]
        positive_records["total"] = len(positives)
        positive_records["passed"] = sum(1 for r in positives if all(run.verdict == "pass" for run in r.runs))
        if positive_records["total"] and positive_records["passed"] < positive_records["total"]:
            failures.append(
                f"正例レコードが judge 集約で全件 pass にならない "
                f"({positive_records['passed']}/{positive_records['total']})"
            )

    return {
        "stage": stage,
        "tpr": tpr,
        "tpr_ci95": tpr_ci,
        "tnr": tnr,
        "tnr_ci95": tnr_ci,
        "positive_records": positive_records,
        "passed": not failures,
        "failures": failures,
    }
