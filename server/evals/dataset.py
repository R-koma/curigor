import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from evals.checks import check_fingerprint
from evals.rubric import load_rubric, merge_assertions
from evals.tools.capture import MAP_ROUTE

GOLDEN_DIR = Path(__file__).parent / "datasets" / "golden"
RUBRIC_DIR = Path(__file__).parent / "datasets" / "rubric"
JSONL_PATH = Path(__file__).parent / "datasets" / "generate_questions.jsonl"

NOT_APPLICABLE = "na"
_VALID_VERDICTS = frozenset({"pass", "fail", NOT_APPLICABLE})


@dataclass(frozen=True)
class SourceTrace:
    trace_id: str
    turn: int
    meta: dict[str, Any]
    input: dict[str, Any]
    observed_output: str
    turn_decision: dict[str, Any] | None = None
    has_turn_decision: bool = False


LEGACY_ROUTE = "legacy"
ALL_ROUTES = "all"
ROUTE_CHOICES = (ALL_ROUTES, MAP_ROUTE, LEGACY_ROUTE)


def trace_route(trace: SourceTrace) -> str:
    return MAP_ROUTE if trace.meta.get("route") == MAP_ROUTE else LEGACY_ROUTE


def route_blocker(trace: SourceTrace, route: str) -> str | None:
    instance_route = trace_route(trace)
    if route in (ALL_ROUTES, instance_route):
        return None
    return f"--route {route} の対象外（{instance_route} の経路）"


def load_golden_records() -> Iterator[dict[str, Any]]:
    """active な golden を、共通 assertion（rubric）を混ぜた状態で返す。"""
    rubric = load_rubric()
    for path in sorted(GOLDEN_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        with path.open(encoding="utf-8") as f:
            record = yaml.safe_load(f)
        if record.get("status") == "active":
            record["assertions"] = merge_assertions(record["assertions"], rubric)
            # instance がまだ 1 件も無いファイルは `instances:` が None になる（起票直後の状態）
            record["instances"] = record["instances"] or []
            yield record


def validate_check_fingerprints() -> dict[str, str]:
    in_use: dict[str, str] = {}
    stale: list[str] = []
    for record in load_golden_records():
        for assertion in record["assertions"]:
            if assertion["type"] != "deterministic":
                continue
            current = check_fingerprint(assertion["check"])
            in_use[assertion["check"]] = current
            if assertion.get("check_fingerprint") != current:
                stale.append(
                    f"  {record['failure_mode']}/{assertion['id']}: check={assertion['check']} "
                    f"recorded={assertion.get('check_fingerprint')!r} current={current!r}"
                )
    if stale:
        raise ValueError(
            "deterministic check の実装が golden 記録時から変わっている。criterion を読み直し、"
            "必要なら human_verdicts を付け直してから check_fingerprint を更新すること:\n" + "\n".join(stale)
        )
    return in_use


def validate_human_verdicts(records: list[dict[str, Any]]) -> None:
    """人間ラベルのキー集合と値を採点前に検証する。

    どちらも壊れても実行時エラーにならない: 余分なキーは誰も読まず、`pass` / `fail` / `na` 以外の値は
    混同行列のどのセルにも入らないまま分母にだけ残り、TPR / TNR と校正ゲートを 100% のまま通す。
    """
    problems: list[str] = []
    for record in records:
        declared = {assertion["id"] for assertion in record["assertions"]}
        for instance in record["instances"]:
            label = f"{record['failure_mode']}/{instance['source_trace_id']}"
            verdicts = instance["human_verdicts"]
            if missing := sorted(declared - set(verdicts)):
                problems.append(f"  {label}: human_verdicts にラベルが無い assertion: {', '.join(missing)}")
            if extra := sorted(set(verdicts) - declared):
                problems.append(f"  {label}: assertions に無い id へのラベル: {', '.join(extra)}")
            problems.extend(
                f"  {label}/{assertion_id}: 不正な verdict {verdict!r}"
                for assertion_id, verdict in sorted(verdicts.items())
                if verdict not in _VALID_VERDICTS
            )
    if problems:
        raise ValueError(
            f"golden の human_verdicts が不正（verdict は {'/'.join(sorted(_VALID_VERDICTS))} のみ）:\n"
            + "\n".join(problems)
        )


def load_source_records() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    with JSONL_PATH.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record: dict[str, Any] = json.loads(line)
                records[record["id"]] = record
    return records


def get_source_trace(trace_id: str, sources: dict[str, dict[str, Any]]) -> SourceTrace:
    try:
        record = sources[trace_id]
    except KeyError as exc:
        raise ValueError(f"unknown source_trace_id: {trace_id} not in {JSONL_PATH}") from exc
    return SourceTrace(
        trace_id=trace_id,
        turn=record["turn"],
        meta=record["meta"],
        input=record["input"],
        observed_output=record["output"],
        turn_decision=record.get("turn_decision"),
        has_turn_decision="turn_decision" in record,
    )


def unannotated_ids(sources: dict[str, dict[str, Any]]) -> list[str]:
    """人間ラベル（`pass`）が付いていないレコードの id。"""
    return [record["id"] for record in sources.values() if record.get("pass") is None]
