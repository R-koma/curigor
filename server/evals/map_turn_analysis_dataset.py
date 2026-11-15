from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, get_args

from evals.dataset import SourceTrace, get_source_trace, trace_route
from evals.replay import replay_blocker
from evals.taxonomy import MAP_ROUTE
from graph.output_schemas import MapUserIntent

DEFAULT_DATASET = Path(__file__).parent / "datasets" / "map_turn_analysis.jsonl"
USER_INTENTS: tuple[str, ...] = get_args(MapUserIntent)
FIELDS: tuple[str, str] = ("has_misconception", "user_intent")
SOURCES: tuple[str, ...] = ("real", "handwritten")


def load_rows(path: Path = DEFAULT_DATASET) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _value_problem(field: str, value: Any) -> str | None:
    if field == "has_misconception":
        return None if isinstance(value, bool) else f"has_misconception は真偽値（{value!r}）"
    return None if value in USER_INTENTS else f"user_intent が不正（{value!r}）"


def validate_row(row: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if row.get("source") not in SOURCES:
        problems.append(f"source は {'/'.join(SOURCES)} のどちらか（{row.get('source')!r}）")
    if not row.get("base"):
        problems.append("base が空")
    if row.get("source") == "handwritten" and not str(row.get("last_user_message") or "").strip():
        problems.append("handwritten は last_user_message が空でないこと")
    unclear = row.get("unclear", [])
    unknown = [f for f in unclear if f not in FIELDS]
    if unknown:
        problems.append(f"unclear に知らない項目がある: {', '.join(unknown)}")
    expected = row.get("expected")
    if expected is None:
        if unclear:
            problems.append("expected が null の行は unclear を持たない")
        return problems
    if not isinstance(expected, dict) or set(expected) != set(FIELDS):
        return [*problems, f"expected は {', '.join(FIELDS)} の 2 項目を持つ dict か null"]
    for field in FIELDS:
        if field in unclear:
            if expected[field] is not None:
                problems.append(f"unclear の {field} の値は null にする（{expected[field]!r}）")
        elif problem := _value_problem(field, expected[field]):
            problems.append(problem)
    return problems


def blocker(trace: SourceTrace) -> str | None:
    if trace_route(trace) != MAP_ROUTE:
        return "地図の経路のレコードでない"
    if reason := replay_blocker(trace, "full"):
        return reason
    if trace.input["graph_state"].get("start_requested"):
        return "質問を始める合図のターンは事前分析を呼ばない"
    return None


def resolve_trace(row: dict[str, Any], sources: dict[str, dict[str, Any]]) -> SourceTrace:
    trace = get_source_trace(row["base"], sources)
    if row["source"] != "handwritten":
        return trace
    graph_input = copy.deepcopy(trace.input)
    graph_input["conversation_history"][-1]["content"] = row["last_user_message"]
    return replace(trace, input=graph_input)


def seed_real_rows(sources: dict[str, dict[str, Any]], existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    taken = {row["base"] for row in existing if row["source"] == "real"}
    return [
        {
            "id": record_id,
            "source": "real",
            "base": record_id,
            "expected": None,
            "unclear": [],
            "note": "",
            "annotated_at": None,
        }
        for record_id in sources
        if record_id not in taken and blocker(get_source_trace(record_id, sources)) is None
    ]
