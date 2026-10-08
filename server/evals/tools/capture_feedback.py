"""学習・復習のセッションの終わりのフィードバックを、理解度の eval 用 jsonl レコードにする。

入力は本番の `analyze_dialogue` → `score_feedback` に渡したもの（会話・ノート・観点マップ）を
チェックポイントと DB から引き、出力は `feedbacks` の行をそのまま写す。人間の仕事は
`human_level` を付けることだけになる。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import asyncpg
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from core.config import DATABASE_URL, REVIEW_TIMEZONE
from core.database import DBConnection
from evals.tools.capture import CAPTURED_BY, MAP_ROUTE, append_records, session_label, split_unseen
from graph.llm import STRUCTURED_MODELS, StructuredTask
from graph.nodes._feedback_assessment import format_note_text
from graph.prompts.feedback import FEEDBACK_PROMPT_FINGERPRINT

SCHEMA_VERSION = 1
LEGACY_ROUTE = "legacy"
FEEDBACK_TASKS: tuple[StructuredTask, ...] = ("analyze-dialogue", "generate-feedback-scores")

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "datasets" / "feedback.jsonl"

_SELECT_FEEDBACKS = """--sql
SELECT
    f.id AS feedback_id,
    f.note_id,
    f.dialogue_session_id,
    f.understanding_level,
    f.strength,
    f.improvements,
    f.improvement_items,
    f.created_at,
    s.session_type,
    s.started_at,
    s.is_trial,
    n.topic AS note_topic,
    n.content AS note_content,
    n.aspect_map,
    n.manually_edited_at,
    EXISTS (
        SELECT 1 FROM feedbacks later WHERE later.note_id = f.note_id AND later.created_at > f.created_at
    ) AS has_later_feedback
FROM feedbacks f
JOIN dialogue_sessions s ON s.id = f.dialogue_session_id
JOIN notes n ON n.id = f.note_id
"""


def _database_url() -> str:
    if DATABASE_URL is None:
        raise RuntimeError("DATABASE_URL is not set")
    return DATABASE_URL


def record_id(label: str) -> str:
    return f"{label}__feedback"


def stale_note_reason(row: dict[str, Any]) -> str | None:
    """評価に使ったノート本文が今の `notes.content` と食い違いうるなら、その理由。"""
    if row["has_later_feedback"]:
        return "後の復習でノートが書き換わっている可能性がある（この後にフィードバックがある）"
    if row["manually_edited_at"] is not None and row["manually_edited_at"] > row["created_at"]:
        return "フィードバックの後にノートが手で編集されている"
    return None


def _json_value(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def conversation(messages: list[Any]) -> list[dict[str, Any]]:
    return [{"role": m.type, "content": deepcopy(m.content)} for m in messages]


def feedback_output(row: dict[str, Any]) -> dict[str, Any]:
    items = _json_value(row["improvement_items"])
    if items is None:
        items = [{"text": text} for text in (row["improvements"] or "").splitlines() if text]
    return {
        "understanding_level": row["understanding_level"],
        "strengths": [text for text in (row["strength"] or "").splitlines() if text],
        "improvements": items,
    }


def route_of(row: dict[str, Any], values: dict[str, Any]) -> str | None:
    if row["session_type"] != "learning":
        return None
    return MAP_ROUTE if "intake_complete" in values else LEGACY_ROUTE


def build_record(row: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    label = session_label(row["dialogue_session_id"], row["started_at"])
    is_learning = row["session_type"] == "learning"
    topic = values.get("topic") if is_learning else row["note_topic"]
    meta: dict[str, Any] = {
        "models": {task: asdict(STRUCTURED_MODELS[task]) for task in FEEDBACK_TASKS},
        "prompt_fingerprint": FEEDBACK_PROMPT_FINGERPRINT,
        "captured_by": CAPTURED_BY,
    }
    route = route_of(row, values)
    if route is not None:
        meta["route"] = route
    if row.get("is_trial"):
        meta["trial"] = True
    graph_input: dict[str, Any] = {
        "topic": topic or row["note_topic"],
        "conversation": conversation(values.get("messages") or []),
        "note_text": format_note_text(row["note_topic"], row["note_content"]),
        "aspect_map": _json_value(row["aspect_map"]),
    }
    if values.get("depth_map"):
        graph_input["depth_map"] = deepcopy(values["depth_map"])
        graph_input["map_covered"] = [dict(c) for c in values.get("map_covered") or []]
    return {
        "id": record_id(label),
        "schema_version": SCHEMA_VERSION,
        "source": "real",
        "session": label,
        "session_type": row["session_type"],
        "dialogue_session_id": str(row["dialogue_session_id"]),
        "note_id": str(row["note_id"]),
        "feedback_id": str(row["feedback_id"]),
        "captured_at": row["created_at"].astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "meta": meta,
        "input": graph_input,
        "output": feedback_output(row),
        "human_level": None,
        "note": "",
        "annotated_at": None,
    }


async def fetch_rows(conn: DBConnection, where: str, *args: Any) -> list[dict[str, Any]]:
    records = await conn.fetch(_SELECT_FEEDBACKS + where, *args)
    return [dict(r) for r in records]


async def final_state(checkpointer: AsyncPostgresSaver, session_id: UUID) -> dict[str, Any] | None:
    config: RunnableConfig = {"configurable": {"thread_id": str(session_id)}}
    checkpoint = await checkpointer.aget_tuple(config)
    if checkpoint is None:
        return None
    return dict(checkpoint.checkpoint["channel_values"])


async def collect(
    checkpointer: AsyncPostgresSaver, rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    for row in rows:
        session_id = row["dialogue_session_id"]
        reason = stale_note_reason(row)
        if reason is not None:
            warnings.append(f"{session_id}: {reason}のでスキップした")
            continue
        values = await final_state(checkpointer, session_id)
        if not values or not values.get("messages"):
            warnings.append(f"{session_id}: チェックポイントに会話が無いのでスキップした")
            continue
        records.append(build_record(row, values))
    return records, warnings


def captured_session_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as f:
        return {json.loads(line)["dialogue_session_id"] for line in f if line.strip()}


def print_rows(rows: list[dict[str, Any]], captured: set[str]) -> None:
    for row in rows:
        started = row["started_at"].astimezone(ZoneInfo(REVIEW_TIMEZONE)).strftime("%Y-%m-%d %H:%M")
        if str(row["dialogue_session_id"]) in captured:
            mark = "captured"
        else:
            mark = "stale   " if stale_note_reason(row) else "--------"
        print(
            f"{row['dialogue_session_id']}  {started}  {row['session_type']:<9} "
            f"{row['understanding_level']:<7} {mark}  {(row['note_topic'] or '')[:30]}"
        )


async def select_rows(conn: DBConnection, args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.session_id is not None:
        rows = await fetch_rows(conn, "WHERE f.dialogue_session_id = $1", args.session_id)
        if not rows:
            raise LookupError(f"フィードバックのあるセッションではない: {args.session_id}")
        return rows
    if args.latest:
        rows = await fetch_rows(conn, "ORDER BY f.created_at DESC LIMIT 1")
        if not rows:
            raise LookupError("フィードバックが 1 件も無い")
        return rows
    return await fetch_rows(conn, "ORDER BY f.created_at DESC LIMIT $1", args.limit)


async def run(args: argparse.Namespace, url: str) -> int:
    conn = await asyncpg.connect(url)
    try:
        rows = await select_rows(conn, args)
        if args.list:
            print_rows(rows, captured_session_ids(args.out))
            return 0
        async with AsyncPostgresSaver.from_conn_string(url) as checkpointer:
            records, warnings = await collect(checkpointer, rows)
    except LookupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        await conn.close()

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    new, skipped = split_unseen(args.out, records)

    if args.dry_run:
        for record in new:
            print(json.dumps(record, ensure_ascii=False, indent=2))
        print(f"dry-run: would append {len(new)} record(s) to {args.out} (skipped {skipped} existing)")
        return 0

    append_records(args.out, new)
    print(f"appended {len(new)} record(s) to {args.out} (skipped {skipped} existing)")
    for record in new:
        print(f"  {record['id']}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="evals.tools.capture_feedback",
        description="学習・復習のセッションのフィードバックを理解度の eval 用 jsonl レコードにする",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--latest", action="store_true", help="直近のフィードバックを対象にする")
    target.add_argument("--session-id", type=UUID, default=None, help="対象セッションの UUID")
    target.add_argument("--recent", action="store_true", help="直近 --limit 件のフィードバックをまとめて対象にする")
    target.add_argument("--list", action="store_true", help="直近 --limit 件のフィードバックを一覧して終了")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="追記先の jsonl")
    parser.add_argument("--dry-run", action="store_true", help="追記せず生成レコードを表示する")
    parser.add_argument("--limit", type=int, default=20, help="--list / --recent の件数")
    return parser.parse_args(argv)


def main() -> None:
    raise SystemExit(asyncio.run(run(parse_args(), _database_url())))


if __name__ == "__main__":
    main()
