from datetime import UTC, datetime
from typing import Any

from langchain_core.language_models import BaseChatModel

from evals.dataset import ALL_ROUTES
from evals.judge import JudgeUsage, judge_model_name
from evals.metrics import (
    assertion_agreement,
    assertion_agreement_rates,
    assertion_pass_rates,
    calibration_gate,
    coverage_stability,
    escalation_summary,
    failure_mode_pass_rates,
    record_agreement,
    rubric_pass_rates,
)
from evals.runner import InstanceResult
from graph.llm import RESPONSE_MODELS
from graph.prompts.map_question import MAP_PROMPT_FINGERPRINT
from graph.prompts.question import PROMPT_FINGERPRINT, PROMPT_VERSION


def _instance_kind(human_pass: bool | None) -> str:
    if human_pass is None:
        return "未ラベル"
    return "正例" if human_pass else "負例"


def print_scoring_summary(report: dict[str, Any]) -> None:
    print("レコード別判定（judge の集約 vs 人間ラベル）")
    for record in report["records"]:
        human = "-" if record["human_pass"] is None else ("pass" if record["human_pass"] else "fail")
        for run in record["runs"]:
            mark = "OK" if human != "-" and run["verdict"] == human else "NG"
            print(
                f"  {record['source_trace_id']:<45} {_instance_kind(record['human_pass']):<6} "
                f"judged={run['verdict']:<5} human={human:<5} {mark}"
            )
    record_agreement_result = report["agreement"]["record"]
    rate = record_agreement_result["agreement_rate"]
    suffix = f" ({rate:.0%})" if rate is not None else ""
    print(f"{' ' * 66}一致 {record_agreement_result['agreed']}/{record_agreement_result['total']}{suffix}")

    print("\nassertion 別 一致")
    for row in report["agreement"]["by_assertion"]:
        print(f"  {row['failure_mode']:<38} {row['assertion_id']:<4} {row['agreed']}/{row['total']}")
        for mismatch in row["mismatches"]:
            print(f"      NG {mismatch['source_trace_id']}  judged={mismatch['judged']} human={mismatch['human']}")

    def _print_agreement(label: str, agreement: dict[str, Any]) -> None:
        matrix = agreement["confusion_matrix"]
        rate = agreement["agreement_rate"]
        suffix = f" ({rate:.0%})" if rate is not None else ""
        print(f"\njudge–人間一致（{label}）: {agreement['agreed']}/{agreement['total']}{suffix}")
        counts = f"TP={matrix['tp']} TN={matrix['tn']} FP={matrix['fp']} FN={matrix['fn']}"
        print(f"  {counts}   （陽性 = 人間ラベル fail）")
        print(f"  TPR={agreement['tpr']:.0%}" if agreement["tpr"] is not None else "  TPR=n/a")
        print(f"  TNR={agreement['tnr']:.0%}" if agreement["tnr"] is not None else "  TNR=n/a")
        print(f"  適用外（applies_when を満たさず採点対象外）: {agreement['not_applicable']} 件")

    screen_model = report["meta"]["judge"]["screen"]
    confirm_model = report["meta"]["judge"]["confirm"]
    cascade_enabled = confirm_model is not None

    if cascade_enabled:
        _print_agreement(f"screen={screen_model} 単体", report["agreement"]["screen_assertion"])
        _print_agreement(f"final（screen={screen_model} → confirm={confirm_model}）", report["agreement"]["assertion"])
    else:
        _print_agreement(f"assertion 単位・judge={screen_model}", report["agreement"]["assertion"])

    if cascade_enabled:
        esc = report["agreement"]["escalations"]
        print(
            f"\nエスカレーション: {esc['escalated']}/{esc['total_judge']} 件"
            f"（fail 確定 {esc['confirmed_fail']} / pass に覆った {esc['overturned_to_pass']}）"
        )
        for item in esc["overturned"]:
            print(f"  覆った: {item['failure_mode']}/{item['source_trace_id']} {item['assertion_id']}")
            print(f"    screen ({screen_model}) : {item['screen_detail']}")
            print(f"    confirm({confirm_model}): {item['confirm_detail']}")

    for stage in (("screen",) if cascade_enabled else ()) + ("final",):
        gate = report["agreement"]["calibration"][stage]
        tpr = f"{gate['tpr']:.0%}" if gate["tpr"] is not None else "n/a"
        tnr = f"{gate['tnr']:.0%}" if gate["tnr"] is not None else "n/a"
        tpr_ci = f" [{gate['tpr_ci95'][0]:.0%},{gate['tpr_ci95'][1]:.0%}]" if gate["tpr_ci95"] else ""
        tnr_ci = f" [{gate['tnr_ci95'][0]:.0%},{gate['tnr_ci95'][1]:.0%}]" if gate["tnr_ci95"] else ""
        status = "PASS" if gate["passed"] else "FAIL"
        print(f"\n校正ゲート（{stage}）: {status}  TPR={tpr}{tpr_ci}  TNR={tnr}{tnr_ci}")
        if stage == "final" and gate["positive_records"]["total"]:
            print(f"  正例レコード: {gate['positive_records']['passed']}/{gate['positive_records']['total']} pass")
        for reason in gate["failures"]:
            print(f"  NG {reason}")

    print_judge_usage(report)


def print_judge_usage(report: dict[str, Any]) -> None:
    usage = report["meta"]["judge_usage"]
    if not usage:
        return
    print("\njudge トークン使用量")
    for model, stats in usage.items():
        cost = f"${stats['estimated_cost_usd']:.4f}" if stats["estimated_cost_usd"] is not None else "n/a"
        print(
            f"  {model:<30} calls={stats['calls']:<4} cache_hits={stats.get('cache_hits', 0):<4} "
            f"input={stats['input_tokens']:<8} output={stats['output_tokens']:<8} cost≈{cost}"
        )


def print_regression_summary(report: dict[str, Any]) -> None:
    meta = report["meta"]
    print(f"失敗モード別 pass 率（{meta['runs']} 回生成 / replay={meta['replay_mode']} / route={meta['route']}）")
    for row in report["aggregate"]["failure_mode_pass_rates"]:
        print(f"  {row['failure_mode']:<38} {row['passed']}/{row['runs']} ({row['pass_rate']:.0%})")

    print("\nassertion 別 pass 率")
    for row in report["aggregate"]["assertion_pass_rates"]:
        rate = f"{row['pass_rate']:.0%}" if row["pass_rate"] is not None else "n/a"
        na = f"  na={row['not_applicable']}" if row["not_applicable"] else ""
        print(
            f"  {row['source_trace_id']:<45} {row['assertion_id']:<4} "
            f"{row['passed']}/{row['runs'] - row['not_applicable']} ({rate}){na}"
        )
    stability = report["aggregate"]["coverage_stability"]
    if stability:
        print("\n観点名の run 間一致（事前分析の揺れ。1.0 なら毎回同じ観点セット）")
        for row in stability:
            print(f"  {row['source_trace_id']:<45} mean_jaccard={row['mean_jaccard']:.2f}")
            for aspects in row["aspect_sets"]:
                print(f"      {aspects}")

    if report["skipped"]:
        print("\n忠実に再現できないためスキップしたインスタンス")
        for item in report["skipped"]:
            print(f"  {item['failure_mode']}/{item['source_trace_id']}: {item['reason']}")
    print("\n人間ラベルが無いため judge–人間一致は算出しない（scoring モードで校正する）。")
    print_judge_usage(report)


def print_summary(report: dict[str, Any]) -> None:
    print("=" * 100)
    if report["meta"]["mode"] == "scoring":
        print_scoring_summary(report)
    else:
        print_regression_summary(report)

    if report["errors"]:
        print("\nエラー")
        for err in report["errors"]:
            print(f"  {err}")


def build_report(
    results: list[InstanceResult],
    errors: list[str],
    *,
    mode: str,
    runs: int,
    fingerprints: dict[str, str],
    judge: BaseChatModel,
    confirm_judge: BaseChatModel | None = None,
    usage: JudgeUsage | None = None,
    skipped: list[dict[str, str]] | None = None,
    replay_mode: str = "full",
    route: str = ALL_ROUTES,
    traces: frozenset[str] | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "meta": {
            "mode": mode,
            "runs": runs if mode == "regression" else 1,
            "replay_mode": replay_mode if mode == "regression" else None,
            "generated_at": datetime.now(UTC).isoformat(),
            "model": RESPONSE_MODELS["learning-dialogue"].model,
            "temperature": RESPONSE_MODELS["learning-dialogue"].temperature,
            "prompt_version": PROMPT_VERSION,
            "prompt_fingerprint": PROMPT_FINGERPRINT,
            "map_prompt_fingerprint": MAP_PROMPT_FINGERPRINT,
            "route": route,
            "traces": sorted(traces) if traces is not None else None,
            "judge_model": judge_model_name(judge),
            "judge": {
                "screen": judge_model_name(judge),
                "confirm": judge_model_name(confirm_judge) if confirm_judge is not None else None,
            },
            "judge_usage": usage.to_report() if usage is not None else {},
            "check_fingerprints": fingerprints,
        },
        "records": [
            {
                "failure_mode": r.failure_mode,
                "source_trace_id": r.source_trace_id,
                "human_pass": r.human_pass,
                "runs": [
                    {
                        "run_index": run.run_index,
                        "verdict": run.verdict,
                        "output": run.output,
                        "turn_analysis": run.generation.turn_analysis if run.generation else None,
                        "covered_aspects": run.generation.covered_aspects if run.generation else None,
                        "map_covered": run.generation.map_covered if run.generation else None,
                        "depth_map": run.generation.depth_map if run.generation else None,
                        "assertions": [
                            {
                                "assertion_id": o.assertion_id,
                                "type": o.assertion_type,
                                "polarity": o.polarity,
                                "holds": o.holds,
                                "judged": o.verdict,
                                "human": o.human_verdict or None,
                                "detail": o.detail,
                                "decided_by": o.decided_by,
                                "screen_holds": o.screen_holds,
                                "screen_detail": o.screen_detail or None,
                            }
                            for o in run.outcomes
                        ],
                    }
                    for run in r.runs
                ],
            }
            for r in results
        ],
        "aggregate": {
            "assertion_pass_rates": assertion_pass_rates(results),
            "rubric_pass_rates": rubric_pass_rates(results),
            "failure_mode_pass_rates": failure_mode_pass_rates(results),
            "coverage_stability": coverage_stability(results),
        },
        "errors": errors,
        "skipped": skipped or [],
    }
    if mode == "scoring":
        report["agreement"] = {
            "assertion": assertion_agreement(results, stage="final"),
            "screen_assertion": assertion_agreement(results, stage="screen"),
            "record": record_agreement(results),
            "by_assertion": assertion_agreement_rates(results),
            "escalations": escalation_summary(results),
            "calibration": {
                "final": calibration_gate(results, stage="final"),
                "screen": calibration_gate(results, stage="screen"),
            },
        }
    return report
