"""地図の経路の事前分析が `has_misconception` と `user_intent` を人の正解どおりに判定するかを測る。

正解は `evals/datasets/map_turn_analysis.jsonl`。`real` と `handwritten` は別々に集計し、合算しない。
分類なので judge は使わない。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections import Counter
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.checkpoint import CheckpointStore, ManifestMismatch, sha256_bytes, write_json
from evals.dataset import SourceTrace, get_source_trace, load_source_records
from evals.llm_usage import print_usage, record_usage, summarize_usage
from evals.map_turn_analysis_dataset import (
    DEFAULT_DATASET,
    FIELDS,
    SOURCES,
    USER_INTENTS,
    blocker,
    load_rows,
    resolve_trace,
    validate_row,
)
from evals.model_override import (
    MAP_TURN_ANALYSIS_TASKS,
    add_model_argument,
    apply_overrides,
    models_meta,
    uncalled_overrides,
)
from evals.replay import to_state
from evals.review_end import AnalysisFailed, format_rate, rate
from graph.llm import STRUCTURED_MODELS, StructuredTask
from graph.nodes._map_dialogue import analyze_map_turn
from graph.prompts.map_turn_analysis import _PHASED_MAP_TURN_ANALYSIS_PROMPT, MAP_TURN_ANALYSIS_PROMPT

__all__ = ["AnalysisFailed", "DEFAULT_DATASET", "USER_INTENTS"]

TASK: StructuredTask = "map-turn-analysis"
_REPORTS_DIR = Path(__file__).parent / "reports"
_CHECKPOINT_KIND = "map_turn_analysis"
_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 1.0

Classifier = Callable[[SourceTrace], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class Prediction:
    record_id: str
    source: str
    category: str | None
    run: int
    predicted: dict[str, Any]
    expected: dict[str, Any]
    unclear: tuple[str, ...]


@dataclass(frozen=True)
class Target:
    row: dict[str, Any]
    trace: SourceTrace
    input_hash: str


def _hash_json(value: Any) -> str:
    return sha256_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True).encode())


async def classify(trace: SourceTrace) -> dict[str, Any]:
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        analysis = await analyze_map_turn(to_state(trace))
        if analysis is not None:
            return {"has_misconception": analysis.has_misconception, "user_intent": analysis.user_intent}
        if attempt < _MAX_ATTEMPTS:
            await asyncio.sleep(_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
    raise AnalysisFailed(f"analyze_map_turn returned None {_MAX_ATTEMPTS} times")


def select_targets(
    rows: list[dict[str, Any]], sources: dict[str, dict[str, Any]]
) -> tuple[list[Target], dict[str, Any]]:
    targets: list[Target] = []
    unlabeled: list[str] = []
    blocked: dict[str, str] = {}
    for row in rows:
        if row["expected"] is None:
            unlabeled.append(row["id"])
            continue
        if row["base"] not in sources:
            blocked[row["id"]] = f"base が generate_questions.jsonl に無い（{row['base']}）"
            continue
        trace = resolve_trace(row, sources)
        if reason := blocker(get_source_trace(row["base"], sources)):
            blocked[row["id"]] = reason
            continue
        targets.append(Target(row, trace, _hash_json(trace.input)))
    return targets, {"unlabeled": unlabeled, "blocked": blocked}


def _prediction(row: dict[str, Any], run: int, decision: dict[str, Any]) -> Prediction:
    return Prediction(
        record_id=row["id"],
        source=row["source"],
        category=row.get("category"),
        run=run,
        predicted={field: decision[field] for field in FIELDS},
        expected={field: row["expected"][field] for field in FIELDS},
        unclear=tuple(row["unclear"]),
    )


async def regenerate(
    targets: list[Target],
    runs: int,
    checkpoint: CheckpointStore,
    classifier: Classifier = classify,
    usage_calls: list[dict[str, Any]] | None = None,
) -> list[Prediction]:
    usage_calls = usage_calls if usage_calls is not None else []
    predictions: list[Prediction] = []
    for target in targets:
        record_id = target.row["id"]
        for run in range(runs):
            saved = checkpoint.load_generation(_CHECKPOINT_KIND, record_id, run)
            if saved is None or saved.get("input_hash") != target.input_hash:
                with record_usage() as recorder:
                    decision = await classifier(target.trace)
                saved = {
                    "input_hash": target.input_hash,
                    **{field: decision[field] for field in FIELDS},
                    "usage": recorder.calls,
                }
                checkpoint.save_generation(_CHECKPOINT_KIND, record_id, run, saved)
            usage_calls.extend(saved.get("usage") or [])
            prediction = _prediction(target.row, run, saved)
            print(f"{record_id} run{run}: {prediction.predicted} (expected: {prediction.expected})")
            predictions.append(prediction)
    return predictions


def _counted(predictions: Iterable[Prediction], field: str) -> list[Prediction]:
    return [p for p in predictions if field not in p.unclear]


def _misjudged_field(p: Prediction, field: str) -> bool:
    return bool(p.predicted[field] != p.expected[field])


def misconception_metrics(predictions: Iterable[Prediction]) -> dict[str, Any]:
    items = _counted(predictions, "has_misconception")
    has_error = [p for p in items if p.expected["has_misconception"]]
    no_error = [p for p in items if not p.expected["has_misconception"]]
    return {
        "total": len(items),
        "accuracy": rate(
            sum(1 for p in items if p.predicted["has_misconception"] == p.expected["has_misconception"]), len(items)
        ),
        "missed": rate(sum(1 for p in has_error if not p.predicted["has_misconception"]), len(has_error)),
        "false_alarm": rate(sum(1 for p in no_error if p.predicted["has_misconception"]), len(no_error)),
    }


def intent_metrics(predictions: Iterable[Prediction]) -> dict[str, Any]:
    items = _counted(predictions, "user_intent")
    confusion: dict[str, Counter[str]] = {}
    for p in items:
        confusion.setdefault(p.expected["user_intent"], Counter())[p.predicted["user_intent"]] += 1
    by_class = {}
    for intent in USER_INTENTS:
        of_class = [p for p in items if p.expected["user_intent"] == intent]
        by_class[intent] = rate(sum(1 for p in of_class if p.predicted["user_intent"] == intent), len(of_class))
    return {
        "total": len(items),
        "accuracy": rate(sum(1 for p in items if not _misjudged_field(p, "user_intent")), len(items)),
        "by_class": by_class,
        "confusion": {expected: dict(counts) for expected, counts in confusion.items()},
    }


def _value_key(value: Any) -> str:
    return json.dumps(value) if isinstance(value, bool) else str(value)


def stability(predictions: Iterable[Prediction]) -> dict[str, Any]:
    by_record: dict[str, list[Prediction]] = {}
    for p in predictions:
        by_record.setdefault(p.record_id, []).append(p)
    repeated = {record_id: items for record_id, items in by_record.items() if len(items) >= 2}
    unstable: dict[str, dict[str, dict[str, int]]] = {}
    for record_id, items in repeated.items():
        for field in FIELDS:
            counts = Counter(_value_key(p.predicted[field]) for p in _counted(items, field))
            if len(counts) > 1:
                unstable.setdefault(record_id, {})[field] = dict(counts)
    return {
        "records": len(repeated),
        "unanimous": rate(len(repeated) - len(unstable), len(repeated)),
        "unstable": unstable,
    }


def _misjudged(p: Prediction) -> bool:
    return any(p.predicted[field] != p.expected[field] for field in FIELDS if field not in p.unclear)


def prompt_sha256() -> str:
    return sha256_bytes((MAP_TURN_ANALYSIS_PROMPT + "\0" + _PHASED_MAP_TURN_ANALYSIS_PROMPT).encode())


def inputs_sha256(targets: list[Target]) -> str:
    return _hash_json({t.row["id"]: t.input_hash for t in targets})


def build_report(
    runs: int,
    targets: list[Target],
    predictions: list[Prediction],
    skipped: dict[str, Any],
    *,
    dataset: Path = DEFAULT_DATASET,
    usage_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    by_source = {}
    for source in SOURCES:
        of_source = [p for p in predictions if p.source == source]
        if of_source:
            by_source[source] = {
                "misconception": misconception_metrics(of_source),
                "intent": intent_metrics(of_source),
                "stability": stability(of_source),
            }
    categories = sorted({p.category for p in predictions if p.category})
    return {
        "meta": {
            "kind": "map_turn_analysis",
            "runs": runs,
            "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "prompt_sha256": prompt_sha256(),
            "model": asdict(STRUCTURED_MODELS[TASK]),
            "models": models_meta(MAP_TURN_ANALYSIS_TASKS),
            "dataset_sha256": sha256_bytes(dataset.read_bytes()),
            "inputs_sha256": inputs_sha256(targets),
            "records": len(targets),
            "skipped": skipped,
        },
        "by_source": by_source,
        "by_category": {
            category: {
                "misconception": misconception_metrics(p for p in predictions if p.category == category),
                "intent": intent_metrics(p for p in predictions if p.category == category),
            }
            for category in categories
        },
        "misjudged": sorted({p.record_id for p in predictions if _misjudged(p)}),
        "predictions": [asdict(p) for p in predictions],
        "usage": summarize_usage(usage_calls or []),
    }


def print_summary(report: dict[str, Any]) -> None:
    meta = report["meta"]
    print(f"\n== map_turn_analysis: {meta['records']} 件 × {meta['runs']} run")
    skipped = meta["skipped"]
    print(f"飛ばした行: 正解が未記入 {len(skipped['unlabeled'])} 件、再現できない {len(skipped['blocked'])} 件")
    for source, value in report["by_source"].items():
        misconception, intent = value["misconception"], value["intent"]
        print(f"\n[{source}]")
        print(f"  誤りの判定の一致: {format_rate(misconception['accuracy'])}")
        print(f"  誤りの見逃し（誤りありを「なし」）: {format_rate(misconception['missed'])}")
        print(f"  誤りの誤検出（誤りなしを「あり」）: {format_rate(misconception['false_alarm'])}")
        print(f"  発言の種類の一致: {format_rate(intent['accuracy'])}")
        for name, class_rate in intent["by_class"].items():
            print(f"    {name}: {format_rate(class_rate)}")
        stable = value["stability"]
        if stable["records"]:
            print(f"  揺れ: 全 run が同じ判定 {format_rate(stable['unanimous'])}")
    if report["misjudged"]:
        print(f"\n取り違えた行: {', '.join(report['misjudged'])}")
    print("\n使用量")
    print_usage(report["usage"])


def build_manifest(runs: int) -> dict[str, Any]:
    return {
        "kind": "map_turn_analysis",
        "runs": runs,
        "prompt_sha256": prompt_sha256(),
        "model": asdict(STRUCTURED_MODELS[TASK]),
        "models": models_meta(MAP_TURN_ANALYSIS_TASKS),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="evals.map_turn_analysis", description="地図の経路の事前分析を人の正解と比べる"
    )
    parser.add_argument("--runs", type=int, default=3, help="同じ発言を判定する回数")
    parser.add_argument("--trace", action="append", default=None, help="対象の行の id（複数指定可）")
    parser.add_argument("--source", choices=SOURCES, default=None, help="この種類の行だけを測る")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--checkpoint-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="レポートの保存先")
    add_model_argument(parser)
    return parser.parse_args(argv)


def _report_skipped(skipped: dict[str, Any]) -> None:
    if skipped["unlabeled"]:
        print(
            f"正解が未記入で飛ばした行: {len(skipped['unlabeled'])} 件（{', '.join(skipped['unlabeled'][:10])} ...）"
        )
    if skipped["blocked"]:
        print(f"再現できず飛ばした行: {len(skipped['blocked'])} 件")
        for row_id, reason in skipped["blocked"].items():
            print(f"  {row_id}: {reason}")


async def run(
    args: argparse.Namespace, classifier: Classifier = classify, sources: dict[str, dict[str, Any]] | None = None
) -> int:
    try:
        overridden = apply_overrides(args.model, MAP_TURN_ANALYSIS_TASKS)
    except ValueError as exc:
        print(f"error: {exc}")
        return 1
    rows = load_rows(args.dataset)
    if problems := [f"{row.get('id')}: {p}" for row in rows for p in validate_row(row)]:
        print("error: データセットの行が不正:\n" + "\n".join(problems))
        return 1
    if args.trace:
        unknown = set(args.trace) - {r["id"] for r in rows}
        if unknown:
            print(f"error: unknown record id: {', '.join(sorted(unknown))}")
            return 1
        rows = [r for r in rows if r["id"] in set(args.trace)]
    if args.source:
        rows = [r for r in rows if r["source"] == args.source]
    targets, skipped = select_targets(rows, load_source_records() if sources is None else sources)
    _report_skipped(skipped)
    if not targets:
        print(f"error: 正解の付いた行が無い: {args.dataset}（annotate の /turn-analysis で付ける）")
        return 1

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    checkpoint = CheckpointStore(args.checkpoint_dir or _REPORTS_DIR / f"{timestamp}-map-turn-analysis-checkpoint")
    print(f"checkpoint: {checkpoint.root}\n")
    usage_calls: list[dict[str, Any]] = []
    try:
        checkpoint.ensure_manifest(build_manifest(args.runs))
        predictions = await regenerate(targets, args.runs, checkpoint, classifier, usage_calls)
    except ManifestMismatch as exc:
        print(f"error: {exc}")
        return 1
    except AnalysisFailed as exc:
        print(f"error: {exc}。保存済みの run は同じ --checkpoint-dir で再開できる")
        return 1

    report = build_report(args.runs, targets, predictions, skipped, dataset=args.dataset, usage_calls=usage_calls)
    print_summary(report)
    out = args.out or _REPORTS_DIR / f"{timestamp}-map-turn-analysis.json"
    write_json(out, report)
    print(f"\nreport: {out}")
    if overridden and (uncalled := uncalled_overrides(overridden, report["usage"])):
        print(f"error: 上書きしたタスクが 1 回も呼ばれなかった: {', '.join(uncalled)}")
        return 1
    return 0


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    raise SystemExit(asyncio.run(run(parse_args())))


if __name__ == "__main__":
    main()
