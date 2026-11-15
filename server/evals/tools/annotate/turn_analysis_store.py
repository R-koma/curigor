from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.map_turn_analysis_dataset import DEFAULT_DATASET, FIELDS, SOURCES, USER_INTENTS, load_rows, resolve_trace
from evals.tools.annotate.feedback_store import map_progress
from evals.tools.annotate.store import _TIMESTAMP_FORMAT, _index_of, _lines, _write_atomically
from graph.prompts.map_turn_analysis import MAP_TURN_ANALYSIS_PROMPT

__all__ = ["DEFAULT_DATASET", "LabelError", "criteria", "detail", "load_rows", "save_label", "sort_key", "summary"]

_CRITERIA = {
    "user_intent": re.compile(r"^1\. `user_intent`.*?(?=^2\. )", re.DOTALL | re.MULTILINE),
    "has_misconception": re.compile(r"^3\. `has_misconception`.*?(?=^4\. )", re.DOTALL | re.MULTILINE),
}


class LabelError(ValueError):
    pass


def criteria() -> dict[str, str]:
    result = {}
    for field, pattern in _CRITERIA.items():
        match = pattern.search(MAP_TURN_ANALYSIS_PROMPT)
        result[field] = match.group(0).strip() if match else ""
    return result


def save_label(
    path: Path,
    row_id: str,
    *,
    has_misconception: bool | None,
    user_intent: str | None,
    unclear: list[str],
    note: str,
    last_user_message: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if unknown := [field for field in unclear if field not in FIELDS]:
        raise LabelError(f"unclear に知らない項目がある: {', '.join(unknown)}")
    values: dict[str, Any] = {"has_misconception": has_misconception, "user_intent": user_intent}
    for field in unclear:
        values[field] = None
    for field in FIELDS:
        if field not in unclear and values[field] is None:
            raise LabelError(f"{field} の値が無い（決められないときは unclear に入れる）")
    if user_intent is not None and "user_intent" not in unclear and user_intent not in USER_INTENTS:
        raise LabelError(f"不正な user_intent {user_intent!r}（{'/'.join(USER_INTENTS)} のみ）")

    lines = _lines(path)
    index = _index_of(lines, row_id, path)
    row: dict[str, Any] = json.loads(lines[index])
    if last_user_message is not None:
        if row["source"] != "handwritten":
            raise LabelError("last_user_message を変えられるのは handwritten の行だけ")
        if not last_user_message.strip():
            raise LabelError("last_user_message が空")
        row["last_user_message"] = last_user_message.strip()
    row["expected"] = {field: values[field] for field in FIELDS}
    row["unclear"] = [field for field in FIELDS if field in unclear]
    row["note"] = note
    row["annotated_at"] = (now or datetime.now(UTC)).strftime(_TIMESTAMP_FORMAT)
    lines[index] = json.dumps(row, ensure_ascii=False) + "\n"
    _write_atomically(path, "".join(lines))
    return row


_LAST_MESSAGE_HEAD = 60


def _last_message(row: dict[str, Any], sources: dict[str, dict[str, Any]]) -> str:
    if row["source"] == "handwritten":
        return str(row["last_user_message"])
    base = sources.get(row["base"])
    return str(base["input"]["conversation_history"][-1]["content"]) if base else ""


def summary(row: dict[str, Any], sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    base = sources.get(row["base"])
    return {
        "id": row["id"],
        "source": row["source"],
        "category": row.get("category"),
        "labeled": row["expected"] is not None,
        "topic": base["input"]["graph_state"].get("topic") if base else None,
        "last_user_message": _last_message(row, sources)[:_LAST_MESSAGE_HEAD],
    }


def sort_key(item: dict[str, Any]) -> tuple[bool, int, str]:
    return (item["labeled"], SOURCES.index(item["source"]), item["id"])


def _model_decision(base: dict[str, Any]) -> dict[str, Any] | None:
    decision = base.get("turn_decision")
    return None if decision is None else {field: decision.get(field) for field in FIELDS}


def detail(row: dict[str, Any], sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """`model_decision` は、ラベルを付けた後の実際の発言の行にだけ入れる（先に見せると正解が今のモデルに寄る）。"""
    trace = resolve_trace(row, sources)
    body: dict[str, Any] = {
        "record": summary(row, sources),
        "topic": trace.input["graph_state"].get("topic"),
        "conversation": trace.input["conversation_history"],
        "map_progress": map_progress(trace.input["graph_state"]),
        "criteria": criteria(),
        "expected": row["expected"],
        "unclear": row["unclear"],
        "note": row.get("note", ""),
        "last_user_message": row.get("last_user_message"),
    }
    if row["source"] == "real" and row["expected"] is not None:
        body["model_decision"] = _model_decision(sources[row["base"]])
    return body
