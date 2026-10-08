"""復習の事前分析が「終えたい」（`ReviewTurnAnalysis.wants_to_end_session`）を正しく判定するかを測る。

手で作った発言と期待する判定（`evals/datasets/review_end.jsonl`）に対して `analyze_review_turn` を
`--runs` 回呼び、一致率・取り違えの向き・判定の揺れを出す。分類なので judge は使わない。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from evals.checkpoint import CheckpointStore, ManifestMismatch, sha256_bytes, write_json
from evals.metrics import wilson_interval
from graph.llm import STRUCTURED_MODELS, StructuredTask
from graph.nodes._review_turn_analysis import analyze_review_turn
from graph.prompts.review_turn_analysis import REVIEW_TURN_ANALYSIS_PROMPT_FINGERPRINT
from graph.state import LearningState

DEFAULT_DATASET = Path(__file__).parent / "datasets" / "review_end.jsonl"
TASK: StructuredTask = "review-turn-analysis"
_REPORTS_DIR = Path(__file__).parent / "reports"
_CHECKPOINT_KIND = "review_end"
_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 1.0


class AnalysisFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class Prediction:
    record_id: str
    category: str
    run: int
    predicted: bool
    expected: bool


def load_records(path: Path = DEFAULT_DATASET) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def to_messages(conversation: list[dict[str, Any]]) -> list[BaseMessage]:
    return [
        HumanMessage(content=m["content"]) if m["role"] == "human" else AIMessage(content=m["content"])
        for m in conversation
    ]


def to_state(record: dict[str, Any]) -> LearningState:
    return cast(LearningState, {"topic": record["topic"], "messages": to_messages(record["conversation"])})


def input_hash(record: dict[str, Any]) -> str:
    payload = {"topic": record["topic"], "conversation": record["conversation"]}
    return sha256_bytes(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode())


async def classify(record: dict[str, Any]) -> bool:
    """`analyze_review_turn` は失敗を None で返す（本番は続ける扱い）ので再試行し、尽きたら実行全体を止める。"""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        analysis = await analyze_review_turn(to_state(record))
        if analysis is not None:
            return analysis.wants_to_end_session
        if attempt < _MAX_ATTEMPTS:
            await asyncio.sleep(_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
    raise AnalysisFailed(f"analyze_review_turn returned None {_MAX_ATTEMPTS} times")


Classifier = Callable[[dict[str, Any]], Any]


async def regenerate(
    records: list[dict[str, Any]],
    runs: int,
    checkpoint: CheckpointStore,
    classifier: Classifier = classify,
) -> list[Prediction]:
    predictions: list[Prediction] = []
    for record in records:
        expected_hash = input_hash(record)
        for run in range(runs):
            saved = checkpoint.load_generation(_CHECKPOINT_KIND, record["id"], run)
            if saved is None or saved.get("input_hash") != expected_hash:
                predicted = await classifier(record)
                saved = {"input_hash": expected_hash, "wants_to_end_session": predicted}
                checkpoint.save_generation(_CHECKPOINT_KIND, record["id"], run, saved)
            prediction = _prediction(record, run, saved["wants_to_end_session"])
            mark = "ok" if prediction.predicted == prediction.expected else "NG"
            print(f"{record['id']} run{run}: {prediction.predicted} (expected: {prediction.expected}) {mark}")
            predictions.append(prediction)
    return predictions


def _prediction(record: dict[str, Any], run: int, predicted: bool) -> Prediction:
    return Prediction(
        record_id=record["id"], category=record["category"], run=run, predicted=predicted, expected=record["expected"]
    )


def _rate(count: int, total: int) -> dict[str, Any]:
    interval = wilson_interval(count, total)
    return {
        "count": count,
        "total": total,
        "rate": count / total if total else None,
        "ci95": list(interval) if interval else None,
    }


def agreement(predictions: Iterable[Prediction]) -> dict[str, Any]:
    """run ごとに 1 件として数える。false_end は続けたいのに終える判定、missed_end は終えたいのに続ける判定。"""
    items = list(predictions)
    should_continue = [p for p in items if not p.expected]
    should_end = [p for p in items if p.expected]
    return {
        "total": len(items),
        "accuracy": _rate(sum(1 for p in items if p.predicted == p.expected), len(items)),
        "false_end": _rate(sum(1 for p in should_continue if p.predicted), len(should_continue)),
        "missed_end": _rate(sum(1 for p in should_end if not p.predicted), len(should_end)),
    }


def stability(predictions: Iterable[Prediction]) -> dict[str, Any]:
    by_record: dict[str, Counter[bool]] = {}
    for p in predictions:
        by_record.setdefault(p.record_id, Counter())[p.predicted] += 1
    repeated = {record_id: counts for record_id, counts in by_record.items() if sum(counts.values()) >= 2}
    unstable = {
        record_id: {"true": counts[True], "false": counts[False]}
        for record_id, counts in repeated.items()
        if len(counts) > 1
    }
    return {
        "records": len(repeated),
        "unanimous": _rate(len(repeated) - len(unstable), len(repeated)),
        "unstable": unstable,
    }


def build_report(runs: int, records: list[dict[str, Any]], predictions: list[Prediction]) -> dict[str, Any]:
    categories = sorted({p.category for p in predictions})
    return {
        "meta": {
            "kind": "review_end",
            "runs": runs,
            "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "prompt_fingerprint": REVIEW_TURN_ANALYSIS_PROMPT_FINGERPRINT,
            "model": asdict(STRUCTURED_MODELS[TASK]),
            "records": len(records),
        },
        "agreement": agreement(predictions),
        "by_category": {
            category: agreement(p for p in predictions if p.category == category) for category in categories
        },
        "misjudged": sorted({p.record_id for p in predictions if p.predicted != p.expected}),
        "stability": stability(predictions),
        "predictions": [asdict(p) for p in predictions],
    }


def _format_rate(value: dict[str, Any]) -> str:
    if not value["total"]:
        return "-（0 件）"
    low, high = value["ci95"]
    return f"{value['rate']:.0%}（{value['count']}/{value['total']}、95% CI {low:.0%}〜{high:.0%}）"


def print_summary(report: dict[str, Any]) -> None:
    meta = report["meta"]
    overall = report["agreement"]
    print(f"\n== review_end: {meta['records']} 件 × {meta['runs']} run")
    print(f"一致: {_format_rate(overall['accuracy'])}")
    print(f"続けたいのに終える判定: {_format_rate(overall['false_end'])}")
    print(f"終えたいのに続ける判定: {_format_rate(overall['missed_end'])}")
    print("\nカテゴリーごとの一致")
    for category, value in report["by_category"].items():
        print(f"  {category}: {_format_rate(value['accuracy'])}")
    if report["misjudged"]:
        print(f"\n取り違えたレコード: {', '.join(report['misjudged'])}")
    stable = report["stability"]
    if stable["records"]:
        print(f"\n揺れ: 全 run が同じ判定 {_format_rate(stable['unanimous'])}")
        for record_id, counts in stable["unstable"].items():
            print(f"  {record_id}: {counts}")


def build_manifest(runs: int) -> dict[str, Any]:
    return {
        "kind": "review_end",
        "runs": runs,
        "prompt_fingerprint": REVIEW_TURN_ANALYSIS_PROMPT_FINGERPRINT,
        "model": asdict(STRUCTURED_MODELS[TASK]),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="evals.review_end", description="復習の「終えたい」の判定を測る")
    parser.add_argument("--runs", type=int, default=3, help="同じ発言を判定する回数")
    parser.add_argument("--trace", action="append", default=None, help="対象のレコード id（複数指定可）")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--checkpoint-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="レポートの保存先")
    return parser.parse_args(argv)


async def run(args: argparse.Namespace, classifier: Classifier = classify) -> int:
    records = load_records(args.dataset)
    if args.trace:
        wanted = set(args.trace)
        unknown = wanted - {r["id"] for r in records}
        if unknown:
            print(f"error: unknown record id: {', '.join(sorted(unknown))}")
            return 1
        records = [r for r in records if r["id"] in wanted]
    if not records:
        print(f"error: レコードが無い: {args.dataset}")
        return 1

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    checkpoint = CheckpointStore(args.checkpoint_dir or _REPORTS_DIR / f"{timestamp}-review-end-checkpoint")
    print(f"checkpoint: {checkpoint.root}\n")
    try:
        checkpoint.ensure_manifest(build_manifest(args.runs))
        predictions = await regenerate(records, args.runs, checkpoint, classifier)
    except ManifestMismatch as exc:
        print(f"error: {exc}")
        return 1
    except AnalysisFailed as exc:
        print(f"error: {exc}。保存済みの run は同じ --checkpoint-dir で再開できる")
        return 1

    report = build_report(args.runs, records, predictions)
    print_summary(report)
    out = args.out or _REPORTS_DIR / f"{timestamp}-review-end.json"
    write_json(out, report)
    print(f"\nreport: {out}")
    return 0


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    raise SystemExit(asyncio.run(run(parse_args())))


if __name__ == "__main__":
    main()
