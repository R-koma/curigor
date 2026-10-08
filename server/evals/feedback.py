"""フィードバックの理解度（`understanding_level`）を、人間のラベル（`human_level`）と比べて測る。

- scoring: 保存済みの出力（本番が付けた理解度）を採点する。API を呼ばない
- regression: 入力から `analyze_dialogue` → `score_feedback` を作り直して採点する。同じ入力を
  `--runs` 回評価し、判定の揺れも出す。ラベルの無いレコードも揺れの集計には使う

`evals/eval.py` の golden・judge の仕組みは使わない。理解度はラベルとの完全一致で決定的に採点できる。
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
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from evals.checkpoint import CheckpointStore, ManifestMismatch, sha256_bytes, write_json
from evals.eval import QuotaExhausted, _is_quota_exhausted, _is_transient, wilson_interval
from evals.tools.capture_feedback import DEFAULT_OUT as DEFAULT_DATASET
from evals.tools.capture_feedback import FEEDBACK_TASKS
from graph.llm import STRUCTURED_MODELS
from graph.nodes._feedback_assessment import analyze_dialogue, format_conversation_history, score_feedback
from graph.prompts.feedback import FEEDBACK_PROMPT_FINGERPRINT

logger = logging.getLogger(__name__)

LEVELS = ("low", "medium", "high")
_RANK = {level: rank for rank, level in enumerate(LEVELS)}
_REPORTS_DIR = Path(__file__).parent / "reports"
_CHECKPOINT_KIND = "feedback"
_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 1.0


@dataclass(frozen=True)
class Prediction:
    record_id: str
    session_type: str
    run: int
    level: str
    human_level: str | None


def load_records(path: Path = DEFAULT_DATASET) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def to_messages(conversation: list[dict[str, Any]]) -> list[BaseMessage]:
    return [
        HumanMessage(content=m["content"]) if m["role"] == "human" else AIMessage(content=m["content"])
        for m in conversation
    ]


def input_hash(record: dict[str, Any]) -> str:
    return sha256_bytes(json.dumps(record["input"], ensure_ascii=False, sort_keys=True).encode())


async def _assess_once(record: dict[str, Any]) -> dict[str, Any]:
    data = record["input"]
    analysis = await analyze_dialogue(data["topic"], format_conversation_history(to_messages(data["conversation"])))
    feedback = await score_feedback(data["topic"], analysis, data["aspect_map"], data["note_text"])
    return {
        "understanding_level": feedback.understanding_level,
        "strengths": feedback.strength,
        "improvements": [p.model_dump() for p in feedback.improvement_points],
        "analysis": analysis.model_dump(),
    }


async def assess(record: dict[str, Any]) -> dict[str, Any]:
    """接続断・レート制限は再試行し、課金枯渇は `QuotaExhausted` で実行全体を止める。"""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return await _assess_once(record)
        except Exception as exc:
            if _is_quota_exhausted(exc):
                raise QuotaExhausted(str(exc)) from exc
            if not _is_transient(exc) or attempt == _MAX_ATTEMPTS:
                raise
            logger.warning("assess attempt %d/%d raised: %s", attempt, _MAX_ATTEMPTS, exc)
            await asyncio.sleep(_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
    raise AssertionError("unreachable")


Assessor = Callable[[dict[str, Any]], Any]


async def regenerate(
    records: list[dict[str, Any]],
    runs: int,
    checkpoint: CheckpointStore,
    errors: list[str],
    assessor: Assessor = assess,
) -> list[Prediction]:
    predictions: list[Prediction] = []
    for record in records:
        expected_hash = input_hash(record)
        for run in range(runs):
            saved = checkpoint.load_generation(_CHECKPOINT_KIND, record["id"], run)
            if saved is None or saved.get("input_hash") != expected_hash:
                try:
                    output = await assessor(record)
                except QuotaExhausted:
                    raise
                except Exception as exc:
                    logger.exception("assess failed: %s run %d", record["id"], run)
                    errors.append(f"{record['id']} run{run}: {type(exc).__name__}: {exc}")
                    continue
                saved = {"input_hash": expected_hash, "output": output}
                checkpoint.save_generation(_CHECKPOINT_KIND, record["id"], run, saved)
            level = saved["output"]["understanding_level"]
            print(f"{record['id']} run{run}: {level} (human: {record.get('human_level') or '-'})")
            predictions.append(_prediction(record, run, level))
    return predictions


def stored_predictions(records: Iterable[dict[str, Any]]) -> list[Prediction]:
    return [_prediction(record, 0, record["output"]["understanding_level"]) for record in records]


def _prediction(record: dict[str, Any], run: int, level: str) -> Prediction:
    return Prediction(
        record_id=record["id"],
        session_type=record["session_type"],
        run=run,
        level=level,
        human_level=record.get("human_level"),
    )


def direction(human_level: str, level: str) -> str:
    diff = _RANK[level] - _RANK[human_level]
    if diff > 0:
        return "lenient"
    if diff < 0:
        return "strict"
    return "agree"


def _rate(count: int, total: int) -> dict[str, Any]:
    interval = wilson_interval(count, total)
    return {
        "count": count,
        "total": total,
        "rate": count / total if total else None,
        "ci95": list(interval) if interval else None,
    }


def agreement(predictions: list[Prediction]) -> dict[str, Any]:
    """人間のラベルがある予測だけを数える。regression では run ごとに 1 件として数える。"""
    labeled = [p for p in predictions if p.human_level is not None]
    directions = Counter(direction(p.human_level, p.level) for p in labeled if p.human_level is not None)
    confusion = {human: dict.fromkeys(LEVELS, 0) for human in LEVELS}
    for p in labeled:
        if p.human_level is not None:
            confusion[p.human_level][p.level] += 1
    human_low = [p for p in labeled if p.human_level == "low"]
    return {
        "labeled": len(labeled),
        "exact": _rate(directions["agree"], len(labeled)),
        "lenient": _rate(directions["lenient"], len(labeled)),
        "strict": _rate(directions["strict"], len(labeled)),
        "low_overrated": _rate(sum(1 for p in human_low if p.level != "low"), len(human_low)),
        "confusion": confusion,
    }


def stability(predictions: list[Prediction]) -> dict[str, Any]:
    by_record: dict[str, Counter[str]] = {}
    for p in predictions:
        by_record.setdefault(p.record_id, Counter())[p.level] += 1
    repeated = {record_id: counts for record_id, counts in by_record.items() if sum(counts.values()) >= 2}
    unstable = {
        record_id: dict(sorted(counts.items(), key=lambda item: _RANK[item[0]]))
        for record_id, counts in repeated.items()
        if len(counts) > 1
    }
    modal_shares = [max(counts.values()) / sum(counts.values()) for counts in repeated.values()]
    return {
        "records": len(repeated),
        "unanimous": _rate(len(repeated) - len(unstable), len(repeated)),
        "mean_modal_share": sum(modal_shares) / len(modal_shares) if modal_shares else None,
        "unstable": unstable,
    }


def build_report(
    mode: str, runs: int, records: list[dict[str, Any]], predictions: list[Prediction], errors: list[str]
) -> dict[str, Any]:
    session_types = sorted({p.session_type for p in predictions})
    return {
        "meta": {
            "kind": "feedback",
            "mode": mode,
            "runs": runs,
            "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "prompt_fingerprint": FEEDBACK_PROMPT_FINGERPRINT,
            "models": _models(),
            "records": len(records),
            "labeled_records": sum(1 for r in records if r.get("human_level")),
        },
        "agreement": agreement(predictions),
        "by_session_type": {
            session_type: agreement([p for p in predictions if p.session_type == session_type])
            for session_type in session_types
        },
        "stability": stability(predictions),
        "predictions": [asdict(p) for p in predictions],
        "errors": errors,
    }


def _models() -> dict[str, Any]:
    return {task: asdict(STRUCTURED_MODELS[task]) for task in FEEDBACK_TASKS}


def _format_rate(value: dict[str, Any]) -> str:
    if not value["total"]:
        return "-（0 件）"
    low, high = value["ci95"]
    return f"{value['rate']:.0%}（{value['count']}/{value['total']}、95% CI {low:.0%}〜{high:.0%}）"


def print_summary(report: dict[str, Any]) -> None:
    meta = report["meta"]
    print(f"\n== feedback {meta['mode']}: {meta['records']} 件（ラベル付き {meta['labeled_records']} 件）")
    sections = [("全体", report["agreement"])]
    sections += [(f"  {name}", value) for name, value in report["by_session_type"].items()]
    for name, value in sections:
        print(f"{name}: 一致 {_format_rate(value['exact'])}")
        print(f"{' ' * len(name)}  甘い {_format_rate(value['lenient'])} / 厳しい {_format_rate(value['strict'])}")
        print(f"{' ' * len(name)}  人間 low → LLM medium 以上 {_format_rate(value['low_overrated'])}")
    print("\n混同行列（行 = 人間、列 = LLM）")
    print("        " + "".join(f"{level:>8}" for level in LEVELS))
    for human, row in report["agreement"]["confusion"].items():
        print(f"{human:>8}" + "".join(f"{row[level]:>8}" for level in LEVELS))
    stable = report["stability"]
    if stable["records"]:
        print(f"\n揺れ: 全 run が同じ判定 {_format_rate(stable['unanimous'])}")
        print(f"      最頻値の割合の平均 {stable['mean_modal_share']:.0%}")
        for record_id, counts in stable["unstable"].items():
            print(f"  {record_id}: {counts}")
    for error in report["errors"]:
        print(f"error: {error}")


def build_manifest(runs: int) -> dict[str, Any]:
    return {"kind": "feedback", "runs": runs, "prompt_fingerprint": FEEDBACK_PROMPT_FINGERPRINT, "models": _models()}


def unannotated_ids(records: list[dict[str, Any]]) -> list[str]:
    return [r["id"] for r in records if not r.get("human_level")]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="evals.feedback", description="フィードバックの理解度を人間のラベルと比べる")
    parser.add_argument("--mode", choices=("scoring", "regression"), default="scoring")
    parser.add_argument("--runs", type=int, default=3, help="regression で同じ入力を評価する回数")
    parser.add_argument("--trace", action="append", default=None, help="対象のレコード id（複数指定可）")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--checkpoint-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="レポートの保存先")
    parser.add_argument("--list-unannotated", action="store_true", help="human_level の無いレコードを一覧して終了")
    return parser.parse_args(argv)


async def run(args: argparse.Namespace, assessor: Assessor = assess) -> int:
    records = load_records(args.dataset)
    if args.list_unannotated:
        for record_id in unannotated_ids(records):
            print(record_id)
        return 0
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
    errors: list[str] = []
    runs = 1
    if args.mode == "scoring":
        predictions = stored_predictions(records)
    else:
        runs = args.runs
        checkpoint = CheckpointStore(args.checkpoint_dir or _REPORTS_DIR / f"{timestamp}-feedback-checkpoint")
        print(f"checkpoint: {checkpoint.root}\n")
        try:
            checkpoint.ensure_manifest(build_manifest(runs))
            predictions = await regenerate(records, runs, checkpoint, errors, assessor)
        except ManifestMismatch as exc:
            print(f"error: {exc}")
            return 1
        except QuotaExhausted as exc:
            print(f"error: quota exhausted。保存済みの run は同じ --checkpoint-dir で再開できる: {exc}")
            return 1

    report = build_report(args.mode, runs, records, predictions, errors)
    print_summary(report)
    out = args.out or _REPORTS_DIR / f"{timestamp}-feedback-{args.mode}.json"
    write_json(out, report)
    print(f"\nreport: {out}")
    return 1 if errors else 0


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    raise SystemExit(asyncio.run(run(parse_args())))


if __name__ == "__main__":
    main()
