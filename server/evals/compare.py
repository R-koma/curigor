"""2 つのレポートの品質（レコードを対にした差と 95% 区間）・料金・待ち時間を比べる。API を呼ばない。"""

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any, Literal, cast

Kind = Literal["eval", "feedback", "review_end"]

_KINDS: tuple[str, ...] = ("eval", "feedback", "review_end")
_MIN_ASSERTION_DELTA = 1e-9

_SAME_CONDITIONS: dict[Kind, tuple[str, ...]] = {
    "eval": (
        "runs",
        "replay_mode",
        "route",
        "traces",
        "prompt_fingerprint",
        "map_prompt_fingerprint",
        "judge",
        "check_fingerprints",
        "dataset_content_sha256",
    ),
    "feedback": ("mode", "runs", "prompt_fingerprint", "dataset_sha256"),
    "review_end": ("runs", "prompt_fingerprint", "dataset_sha256"),
}

_METRICS: dict[Kind, tuple[tuple[str, bool], ...]] = {
    "eval": (("all_pass", True),),
    "feedback": (("exact", True), ("low_overrated", False)),
    "review_end": (("accuracy", True), ("false_end", False), ("missed_end", False)),
}

_VERDICT_WORDS = {"improved": "改善", "regressed": "悪化", "within_noise": "揺れの範囲"}


def report_kind(report: dict[str, Any]) -> Kind:
    kind = report.get("meta", {}).get("kind", "eval")
    if kind not in _KINDS:
        raise ValueError(f"知らない種類のレポート: {kind!r}（{', '.join(_KINDS)} のどれか）")
    return cast(Kind, kind)


def _record_run_counts(report: dict[str, Any], kind: Kind) -> dict[str, int]:
    counts: dict[str, int] = {}
    if kind == "eval":
        for record in report["records"]:
            counts[f"{record['failure_mode']}/{record['source_trace_id']}"] = len(record["runs"])
    else:
        for prediction in report["predictions"]:
            counts[prediction["record_id"]] = counts.get(prediction["record_id"], 0) + 1
    return counts


def _names(keys: set[str]) -> str:
    shown = sorted(keys)[:5]
    return "、".join(shown) + (f" ほか {len(keys) - 5} 件" if len(keys) > 5 else "")


def comparability(base: dict[str, Any], candidate: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(止める理由, 警告)。"""
    kinds = (report_kind(base), report_kind(candidate))
    if kinds[0] != kinds[1]:
        return [f"レポートの種類が違う: {kinds[0]} と {kinds[1]}"], []
    kind = kinds[0]
    blockers: list[str] = []
    warnings: list[str] = []
    base_meta, candidate_meta = base["meta"], candidate["meta"]

    if kind in ("eval", "feedback"):
        for label, meta in (("基準", base_meta), ("候補", candidate_meta)):
            if meta.get("mode") != "regression":
                blockers.append(f"{label}が regression のレポートでない（mode={meta.get('mode')}）")

    for key in _SAME_CONDITIONS[kind]:
        if key not in base_meta or key not in candidate_meta:
            warnings.append(f"{key} がどちらかのレポートに無く、同じ条件か確かめられない")
        elif base_meta[key] != candidate_meta[key]:
            blockers.append(f"{key} が違う: 基準 {base_meta[key]!r} / 候補 {candidate_meta[key]!r}")

    base_counts, candidate_counts = _record_run_counts(base, kind), _record_run_counts(candidate, kind)
    if only := set(base_counts) ^ set(candidate_counts):
        blockers.append(f"片方にしか無いレコードがある（{len(only)} 件）: {_names(only)}")
    if unequal := {
        key for key in set(base_counts) & set(candidate_counts) if base_counts[key] != candidate_counts[key]
    }:
        blockers.append(f"同じレコードの run の数が違う（{len(unequal)} 件）: {_names(unequal)}")

    if _models_of(base) is None or _models_of(candidate) is None:
        warnings.append("meta.models が無いレポートがあり、モデルの差を確かめられない")
    elif not model_diff(base, candidate):
        warnings.append("モデルの設定が同じ。揺れの幅の計測として読む")
    if base.get("usage") is None or candidate.get("usage") is None:
        warnings.append("usage が無いレポートがあり、料金と時間は比べられない（記録なし）")
    return blockers, warnings


def _models_of(report: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
    meta = report["meta"]
    if meta.get("models"):
        return cast(dict[str, dict[str, Any]], meta["models"])
    kind = report_kind(report)
    if kind == "eval" and "model" in meta:
        return {"learning-dialogue": {"model": meta["model"], "temperature": meta.get("temperature")}}
    if kind == "review_end" and isinstance(meta.get("model"), dict):
        return {"review-turn-analysis": meta["model"]}
    return None


def model_diff(base: dict[str, Any], candidate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    base_models, candidate_models = _models_of(base) or {}, _models_of(candidate) or {}
    diff: dict[str, dict[str, Any]] = {}
    for task in sorted(set(base_models) | set(candidate_models)):
        before, after = base_models.get(task), candidate_models.get(task)
        if before is None or after is None or any(before[key] != after[key] for key in before.keys() & after.keys()):
            diff[task] = {"base": before, "candidate": after}
    return diff


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _by_record(pairs: list[tuple[str, float]]) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for key, value in pairs:
        grouped.setdefault(key, []).append(value)
    return {key: _mean(values) for key, values in grouped.items()}


def record_scores(report: dict[str, Any], metric: str) -> dict[str, float]:
    """レコードのキー -> run の平均（0〜1）。"""
    if metric == "all_pass":
        return {
            f"{record['failure_mode']}/{record['source_trace_id']}": _mean(
                [1.0 if run["verdict"] == "pass" else 0.0 for run in record["runs"]]
            )
            for record in report["records"]
            if record["runs"]
        }
    predictions: list[dict[str, Any]] = report["predictions"]
    pairs: list[tuple[str, float]]
    if metric == "exact":
        pairs = [(p["record_id"], float(p["level"] == p["human_level"])) for p in predictions if p["human_level"]]
    elif metric == "low_overrated":
        pairs = [(p["record_id"], float(p["level"] != "low")) for p in predictions if p["human_level"] == "low"]
    elif metric == "accuracy":
        pairs = [(p["record_id"], float(p["predicted"] == p["expected"])) for p in predictions]
    elif metric == "false_end":
        pairs = [(p["record_id"], float(p["predicted"])) for p in predictions if not p["expected"]]
    elif metric == "missed_end":
        pairs = [(p["record_id"], float(not p["predicted"])) for p in predictions if p["expected"]]
    else:
        raise ValueError(f"知らない指標: {metric}")
    return _by_record(pairs)


def paired_delta(
    base: dict[str, float],
    candidate: dict[str, float],
    *,
    higher_is_better: bool = True,
    resamples: int = 2000,
    seed: int = 0,
) -> dict[str, Any]:
    keys = sorted(base.keys() & candidate.keys())
    if not keys:
        return {"records": 0, "base": None, "candidate": None, "delta": None, "ci95": None, "verdict": "within_noise"}
    diffs = [candidate[key] - base[key] for key in keys]
    rng = random.Random(seed)  # noqa: S311
    means = sorted(_mean([rng.choice(diffs) for _ in diffs]) for _ in range(resamples))
    low = means[math.floor(0.025 * resamples)]
    high = means[math.ceil(0.975 * resamples) - 1]
    if low <= 0 <= high:
        verdict = "within_noise"
    else:
        improved = low > 0
        verdict = "improved" if improved == higher_is_better else "regressed"
    return {
        "records": len(keys),
        "base": _mean([base[key] for key in keys]),
        "candidate": _mean([candidate[key] for key in keys]),
        "delta": _mean(diffs),
        "ci95": [low, high],
        "verdict": verdict,
    }


def _rates_by(report: dict[str, Any], section: str, key: str) -> dict[str, float | None]:
    return {row[key]: row["pass_rate"] for row in report["aggregate"].get(section, [])}


def _rate_deltas(base: dict[str, float | None], candidate: dict[str, float | None]) -> list[dict[str, Any]]:
    rows = []
    for name in sorted(base.keys() | candidate.keys()):
        before, after = base.get(name), candidate.get(name)
        delta = None if before is None or after is None else after - before
        rows.append({"name": name, "base": before, "candidate": after, "delta": delta})
    return rows


def _eval_breakdown(base: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    base_scores, candidate_scores = record_scores(base, "all_pass"), record_scores(candidate, "all_pass")
    changes: list[dict[str, Any]] = sorted(
        (
            {"record": key, "base": base_scores[key], "candidate": candidate_scores[key]}
            for key in base_scores.keys() & candidate_scores.keys()
            if abs(candidate_scores[key] - base_scores[key]) > _MIN_ASSERTION_DELTA
        ),
        key=lambda row: (-abs(row["candidate"] - row["base"]), row["record"]),
    )
    return {
        "failure_modes": _rate_deltas(
            _rates_by(base, "failure_mode_pass_rates", "failure_mode"),
            _rates_by(candidate, "failure_mode_pass_rates", "failure_mode"),
        ),
        "rubric_assertions": _rate_deltas(
            _rates_by(base, "rubric_pass_rates", "assertion_id"),
            _rates_by(candidate, "rubric_pass_rates", "assertion_id"),
        ),
        "regressed_records": [row for row in changes if row["candidate"] < row["base"]],
        "improved_records": [row for row in changes if row["candidate"] > row["base"]],
    }


def _ratio(before: float | None, after: float | None) -> float | None:
    if before is None or after is None or before == 0:
        return None
    return after / before


def _usage_comparison(base: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any] | None:
    base_usage, candidate_usage = base.get("usage"), candidate.get("usage")
    if base_usage is None or candidate_usage is None:
        return None
    tasks: dict[str, Any] = {}
    for task in sorted(base_usage["tasks"].keys() | candidate_usage["tasks"].keys()):
        before, after = base_usage["tasks"].get(task, {}), candidate_usage["tasks"].get(task, {})
        tasks[task] = {
            field: {
                "base": before.get(field),
                "candidate": after.get(field),
                "ratio": _ratio(before.get(field), after.get(field)),
            }
            for field in ("cost_per_call_usd", "seconds_p50")
        }
        tasks[task]["calls"] = {"base": before.get("calls"), "candidate": after.get("calls")}
    return {"tasks": tasks}


def compare(base: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    blockers, warnings = comparability(base, candidate)
    kind = report_kind(base)
    result: dict[str, Any] = {
        "kind": kind,
        "blockers": blockers,
        "warnings": warnings,
        "model_diff": model_diff(base, candidate),
        "metrics": {},
        "primary": _METRICS[kind][0][0],
        "breakdown": None,
        "stability": None,
        "usage": None,
    }
    if kind != report_kind(candidate):
        return result
    for metric, higher_is_better in _METRICS[kind]:
        result["metrics"][metric] = paired_delta(
            record_scores(base, metric), record_scores(candidate, metric), higher_is_better=higher_is_better
        )
    if kind == "eval":
        result["breakdown"] = _eval_breakdown(base, candidate)
    else:
        before = base["stability"]["unanimous"]["rate"]
        after = candidate["stability"]["unanimous"]["rate"]
        result["stability"] = {
            "base": before,
            "candidate": after,
            "delta": None if None in (before, after) else after - before,
        }
    result["usage"] = _usage_comparison(base, candidate)
    return result


def _points(value: float | None) -> str:
    if value is None:
        return "-"
    points = round(value * 100, 1)
    return "0.0" if points == 0 else f"{points:+.1f}".replace("-", "−")


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{value:.1%}"


def _ratio_text(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f} 倍"


def _print_metric(name: str, value: dict[str, Any]) -> None:
    if value["delta"] is None:
        print(f"  {name}: 比べるレコードが無い")
        return
    low, high = value["ci95"]
    print(
        f"  {name}: {_percent(value['base'])} → {_percent(value['candidate'])}  "
        f"差 {_points(value['delta'])} ポイント（95% 区間 {_points(low)}〜{_points(high)}）: "
        f"{_VERDICT_WORDS[value['verdict']]}（{value['records']} レコード）"
    )


def _print_breakdown(breakdown: dict[str, Any]) -> None:
    print("\n内訳（区間なし）")
    for title, rows in (
        ("failure_mode", breakdown["failure_modes"]),
        ("rubric の assertion", breakdown["rubric_assertions"]),
    ):
        changed = [row for row in rows if row["delta"]]
        print(f"  {title}ごとの差" + ("" if changed else ": 変化なし"))
        for row in changed:
            before, after, delta = _percent(row["base"]), _percent(row["candidate"]), _points(row["delta"])
            print(f"    {row['name']}: {before} → {after}（{delta} ポイント）")
    for title, rows in (
        ("悪化したレコード", breakdown["regressed_records"]),
        ("改善したレコード", breakdown["improved_records"]),
    ):
        print(f"  {title}: {len(rows)} 件")
        for row in rows:
            print(f"    {row['record']}: {_percent(row['base'])} → {_percent(row['candidate'])}")


def _print_usage(usage: dict[str, Any] | None) -> None:
    print("\n料金と時間")
    if usage is None:
        print("  記録なし")
        return
    for task, stats in usage["tasks"].items():
        cost, seconds, calls = stats["cost_per_call_usd"], stats["seconds_p50"], stats["calls"]
        cost_text = f"${cost['base'] or 0:.5f} → ${cost['candidate'] or 0:.5f}（{_ratio_text(cost['ratio'])}）"
        base_seconds, candidate_seconds = seconds["base"] or 0, seconds["candidate"] or 0
        seconds_text = f"{base_seconds:.1f}s → {candidate_seconds:.1f}s（{_ratio_text(seconds['ratio'])}）"
        counts = f"{calls['base']} → {calls['candidate']}"
        print(f"  {task}: 1 回あたり {cost_text} / 中央値 {seconds_text} / 回数 {counts}")


def print_comparison(result: dict[str, Any]) -> None:
    print("比べられるかの確認")
    if not result["blockers"] and not result["warnings"]:
        print("  条件は同じ")
    for reason in result["blockers"]:
        print(f"  止める理由: {reason}")
    for warning in result["warnings"]:
        print(f"  警告: {warning}")

    print("\nモデルの差")
    if not result["model_diff"]:
        print("  なし")
    for task, pair in result["model_diff"].items():
        print(f"  {task}: {pair['base']} → {pair['candidate']}")

    print("\n品質の差")
    primary = result["primary"]
    ordered = [primary, *(name for name in result["metrics"] if name != primary)]
    for name in ordered:
        if name in result["metrics"]:
            _print_metric(name, result["metrics"][name])
    if result["breakdown"] is not None:
        _print_breakdown(result["breakdown"])
    if result["stability"] is not None:
        stability = result["stability"]
        print(f"\n揺れ（全 run が同じ判定の割合）: {_percent(stability['base'])} → {_percent(stability['candidate'])}")
    _print_usage(result["usage"])


def _write_json(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="evals.compare", description="2 つの eval レポートを比べる（API を呼ばない）"
    )
    parser.add_argument("base", type=Path, help="基準のレポート")
    parser.add_argument("candidate", type=Path, help="候補のレポート")
    parser.add_argument("--force", action="store_true", help="条件が違っても比べる")
    parser.add_argument("--out", type=Path, default=None, help="比較の結果を JSON で書く")
    args = parser.parse_args(argv)

    base = json.loads(args.base.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    try:
        result = compare(base, candidate)
    except ValueError as exc:
        print(f"error: {exc}")
        return 1
    print_comparison(result)
    if args.out is not None:
        _write_json(args.out, result)
    kind_differs = report_kind(base) != report_kind(candidate)
    if kind_differs or (result["blockers"] and not args.force):
        print(
            "\nこの条件では比べない。違いを承知で見るときは --force を付ける"
            if not kind_differs
            else "\n種類が違うので比べられない"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
