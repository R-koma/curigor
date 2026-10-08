"""フィードバックの jsonl の人間のラベル（`human_level` / `note` / `annotated_at`）の読み書き。"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.feedback import LEVELS
from evals.tools.annotate.store import _TIMESTAMP_FORMAT, _index_of, _lines, _write_atomically
from evals.tools.capture_feedback import DEFAULT_OUT as DEFAULT_FEEDBACK_JSONL_PATH
from graph.aspect_map import iter_aspects
from graph.depth_map import STAGE_LABELS
from graph.prompts.feedback import GENERATE_FEEDBACK_PROMPT

__all__ = [
    "DEFAULT_FEEDBACK_JSONL_PATH",
    "LabelError",
    "level_criteria",
    "load_records",
    "map_progress",
    "note_aspects",
    "save_label",
]

_CRITERIA = re.compile(r"### understanding_level（理解度）\n(.*?)\n\n", re.DOTALL)


class LabelError(ValueError):
    pass


def load_records(path: Path = DEFAULT_FEEDBACK_JSONL_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in _lines(path) if line.strip()]


def level_criteria() -> str:
    """本番の評価のプロンプトにある 3 段階の基準。人間も同じ物差しで付けるために見せる。"""
    match = _CRITERIA.search(GENERATE_FEEDBACK_PROMPT)
    return match.group(1) if match else ""


def note_aspects(aspect_map: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [{"name": ref.name, "depth": ref.depth} for ref in iter_aspects(aspect_map or {"aspects": []})]


def map_progress(graph_input: dict[str, Any]) -> list[dict[str, Any]] | None:
    """地図の経路の学習で、対話中に溜まった観点ごとの到達段階。復習・旧経路は None。"""
    depth_map = graph_input.get("depth_map")
    if not depth_map:
        return None
    reached = {c["aspect_id"]: c["reached_stage"] for c in graph_input.get("map_covered") or []}
    return [
        {
            "name": aspect["name"],
            "is_core": bool(aspect.get("is_core")),
            "stage": STAGE_LABELS.get(reached[aspect["id"]]) if aspect["id"] in reached else None,
        }
        for aspect in depth_map["aspects"]
    ]


def save_label(
    path: Path, record_id: str, human_level: str | None, note: str, *, now: datetime | None = None
) -> dict[str, Any]:
    if human_level is not None and human_level not in LEVELS:
        raise LabelError(f"不正な human_level {human_level!r}（{'/'.join(LEVELS)} のみ）")
    lines = _lines(path)
    index = _index_of(lines, record_id, path)
    record: dict[str, Any] = json.loads(lines[index])
    record["human_level"] = human_level
    record["note"] = note
    record["annotated_at"] = None if human_level is None else (now or datetime.now(UTC)).strftime(_TIMESTAMP_FORMAT)
    lines[index] = json.dumps(record, ensure_ascii=False) + "\n"
    _write_atomically(path, "".join(lines))
    return record
