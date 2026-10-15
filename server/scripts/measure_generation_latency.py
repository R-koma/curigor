"""終了後の学習メモ・ノートの作成時間を、完了済みセッションの state を固定の入力にして計測する。

LLM を呼ぶので課金がかかる。作ったノート・学習メモは計測ごとに消す。

`uv run python -m scripts.measure_generation_latency list`
`uv run python -m scripts.measure_generation_latency run --session <id> --runs 5`
`uv run python -m scripts.measure_generation_latency run --same-as <report.json>`
`uv run python -m scripts.measure_generation_latency compare <before.json> <after.json>`
"""

import argparse
import asyncio
import json
import statistics
import subprocess
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.runnables import RunnableLambda

import graph.nodes.generate_note as generate_note_module
from core.database import close_pool, get_pool
from graph.builder import build_learning_graph
from graph.checkpointer import get_checkpointer
from graph.nodes.generate_feedback import generate_feedback
from graph.nodes.generate_note import generate_note
from graph.nodes.generate_study_memo import generate_study_memo
from graph.version import GRAPH_VERSION
from repositories import dialogue_session_repository, note_repository

REPORT_DIR = Path(__file__).resolve().parent.parent / "latency_reports"
MEASURED_KINDS = ("learning", "explore")


@dataclass
class CallTiming:
    name: str
    start_s: float
    duration_s: float


@dataclass(eq=False)
class CallRecorder(AsyncCallbackHandler):
    origin: float = field(default_factory=time.perf_counter)
    calls: list[CallTiming] = field(default_factory=list)
    _open: dict[UUID, tuple[str, float]] = field(default_factory=dict)

    async def on_chain_start(
        self, serialized: dict[str, Any] | None, inputs: Any, *, run_id: UUID, name: str | None = None, **kwargs: Any
    ) -> None:
        if name and "-" in name and not name.endswith("-graph"):
            self._open[run_id] = (name, time.perf_counter())

    async def on_chain_end(self, outputs: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._close(run_id)

    async def on_chain_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._close(run_id)

    def _close(self, run_id: UUID) -> None:
        opened = self._open.pop(run_id, None)
        if opened is None:
            return
        name, started = opened
        self.calls.append(CallTiming(name, round(started - self.origin, 3), round(time.perf_counter() - started, 3)))


async def _timed(
    node: Callable[[Any], Awaitable[dict[str, Any]]], state: dict[str, Any], recorder: CallRecorder
) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    result = await RunnableLambda(node).ainvoke(state, config={"callbacks": [recorder]})
    return result, round(time.perf_counter() - started, 3)


def _skip_embedding(*args: Any, **kwargs: Any) -> None:
    return None


def state_after_note(values: dict[str, Any], note_result: dict[str, Any]) -> dict[str, Any]:
    return {**values, **note_result}


async def _measure_learning(values: dict[str, Any]) -> dict[str, Any]:
    recorder = CallRecorder()
    started = time.perf_counter()
    note_result, note_s = await _timed(generate_note, values, recorder)
    note_id = note_result["note_id"]
    try:
        _, feedback_s = await _timed(generate_feedback, state_after_note(values, note_result), recorder)
    finally:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await note_repository.delete(conn, note_id, values["user_id"])
    total_s = round(time.perf_counter() - started, 3)
    return {"total_s": total_s, "nodes": {"generate_note": note_s, "generate_feedback": feedback_s}, "calls": recorder}


async def _measure_explore(values: dict[str, Any]) -> dict[str, Any]:
    recorder = CallRecorder()
    temp_session_id = uuid.uuid4()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await dialogue_session_repository.create(
            conn, temp_session_id, values["user_id"], "explore", GRAPH_VERSION, topic=values.get("topic")
        )
    try:
        started = time.perf_counter()
        _, memo_s = await _timed(generate_study_memo, {**values, "dialogue_session_id": temp_session_id}, recorder)
        total_s = round(time.perf_counter() - started, 3)
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM dialogue_sessions WHERE id = $1", temp_session_id)
    return {"total_s": total_s, "nodes": {"generate_study_memo": memo_s}, "calls": recorder}


_MEASURERS = {"learning": _measure_learning, "explore": _measure_explore}


async def _load_states(graph: Any, session_ids: list[str]) -> list[tuple[str, str, dict[str, Any]]]:
    loaded = []
    for session_id in session_ids:
        snapshot = await graph.aget_state({"configurable": {"thread_id": session_id}})
        values = dict(snapshot.values)
        kind = values.get("session_type")
        if kind not in MEASURED_KINDS:
            raise SystemExit(f"{session_id}: session_type {kind!r} is not measured (learning / explore only)")
        loaded.append((session_id, str(kind), values))
    return loaded


def _git_commit() -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=False).stdout.strip()  # noqa: S603, S607

    return {"commit": git("rev-parse", "--short", "HEAD"), "dirty": bool(git("status", "--porcelain", "--", "."))}


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    by_session: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        by_session.setdefault(run["session_id"], []).append(run)
    sessions = {}
    for session_id, session_runs in by_session.items():
        totals = [r["total_s"] for r in session_runs]
        call_durations: dict[str, list[float]] = {}
        for r in session_runs:
            for call in r["calls"]:
                call_durations.setdefault(call["name"], []).append(call["duration_s"])
        sessions[session_id] = {
            "kind": session_runs[0]["kind"],
            "messages": session_runs[0]["messages"],
            "runs": len(totals),
            "median_s": round(statistics.median(totals), 3),
            "min_s": min(totals),
            "max_s": max(totals),
            "calls_median_s": {name: round(statistics.median(d), 3) for name, d in sorted(call_durations.items())},
        }
    kinds = {}
    for kind in MEASURED_KINDS:
        totals = [r["total_s"] for r in runs if r["kind"] == kind]
        if totals:
            kinds[kind] = {"runs": len(totals), "median_s": round(statistics.median(totals), 3), "max_s": max(totals)}
    return {"sessions": sessions, "kinds": kinds}


def _change(before: float, after: float) -> str:
    diff = after - before
    ratio = f"{diff / before * 100:+.1f}%" if before else "-"
    return f"{diff:+.2f} s ({ratio})"


def _row(label: str, before_s: float, after_s: float) -> str:
    return f"| {label} | {before_s:.2f} s | {after_s:.2f} s | {_change(before_s, after_s)} |"


def _call_median(report: dict[str, Any], name: str) -> str:
    values = [s["calls_median_s"][name] for s in report["summary"]["sessions"].values() if name in s["calls_median_s"]]
    return f"{statistics.median(values):.2f} s" if values else "-"


def compare(before: dict[str, Any], after: dict[str, Any]) -> str:
    lines = [
        f"`{before['git']['commit']}` → `{after['git']['commit']}`（各 {after['runs_per_session']} 回の中央値）",
        "",
        "| 対象 | 実装前 | 実装後 | 差 |",
        "| --- | --- | --- | --- |",
    ]
    for kind in MEASURED_KINDS:
        b = before["summary"]["kinds"].get(kind)
        a = after["summary"]["kinds"].get(kind)
        if b and a:
            lines.append(_row(f"{kind}（全体）", b["median_s"], a["median_s"]))
    for session_id, b in before["summary"]["sessions"].items():
        a = after["summary"]["sessions"].get(session_id)
        if a:
            lines.append(_row(f"{b['kind']} `{session_id[:8]}`（{b['messages']} 発言）", b["median_s"], a["median_s"]))
    lines += ["", "| 呼び出し | 実装前 | 実装後 |", "| --- | --- | --- |"]
    names = sorted(
        {n for report in (before, after) for s in report["summary"]["sessions"].values() for n in s["calls_median_s"]}
    )
    for name in names:
        lines.append(f"| `{name}` | {_call_median(before, name)} | {_call_median(after, name)} |")
    return "\n".join(lines)


async def _list_sessions(limit: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """--sql
            SELECT s.id, s.session_type, s.topic, s.ended_at,
                   (SELECT COUNT(*) FROM dialogue_messages m WHERE m.dialogue_session_id = s.id) AS messages
            FROM dialogue_sessions s
            WHERE s.status = 'completed'
              AND ((s.session_type = 'learning' AND s.note_id IS NOT NULL)
                OR (s.session_type = 'explore' AND EXISTS (
                    SELECT 1 FROM study_memos sm WHERE sm.dialogue_session_id = s.id)))
            ORDER BY s.ended_at DESC
            LIMIT $1
            """,
            limit,
        )
    await close_pool()
    for row in rows:
        ended = row["ended_at"].strftime("%Y-%m-%d") if row["ended_at"] else "-"
        print(f"{row['id']}  {row['session_type']:<8}  {row['messages']:>3} 発言  {ended}  {row['topic'] or ''}")


async def _run(session_ids: list[str], runs: int, out: Path | None) -> Path:
    vars(generate_note_module)["schedule_note_embedding"] = _skip_embedding
    async with get_checkpointer() as checkpointer:
        graph = build_learning_graph(checkpointer)
        states = await _load_states(graph, session_ids)
    pool = await get_pool()
    records = []
    for session_id, kind, values in states:
        async with pool.acquire() as conn:
            messages = await conn.fetchval(
                "SELECT COUNT(*) FROM dialogue_messages WHERE dialogue_session_id = $1", UUID(session_id)
            )
        for index in range(runs):
            measured = await _MEASURERS[kind](values)
            recorder: CallRecorder = measured.pop("calls")
            measured["calls"] = [vars(c) for c in sorted(recorder.calls, key=lambda c: c.start_s)]
            records.append({"session_id": session_id, "kind": kind, "messages": messages, "run": index + 1} | measured)
            print(f"{kind} {session_id[:8]} run {index + 1}/{runs}: {measured['total_s']:.2f} s")
    await close_pool()
    git = _git_commit()
    report = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": git,
        "runs_per_session": runs,
        "session_ids": session_ids,
        "summary": summarize(records),
        "runs": records,
    }
    REPORT_DIR.mkdir(exist_ok=True)
    path = out or REPORT_DIR / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{git['commit']}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    list_parser = sub.add_parser("list", help="計測に使える完了済みセッション（ノート・学習メモがあるもの）を出す")
    list_parser.add_argument("--limit", type=int, default=30)
    run_parser = sub.add_parser("run", help="セッションの state で作成を繰り返し、時間を記録する")
    run_parser.add_argument("--session", action="append", default=[], help="対話セッションの ID（複数回指定できる）")
    run_parser.add_argument("--same-as", type=Path, help="前のレポートと同じセッション・回数で計測する")
    run_parser.add_argument("--runs", type=int, default=None, help="セッションごとの回数（既定 5）")
    run_parser.add_argument("--out", type=Path, default=None)
    compare_parser = sub.add_parser("compare", help="2 つのレポートの中央値を Markdown の表で並べる")
    compare_parser.add_argument("before", type=Path)
    compare_parser.add_argument("after", type=Path)
    args = parser.parse_args()

    if args.command == "list":
        asyncio.run(_list_sessions(args.limit))
    elif args.command == "run":
        session_ids = list(args.session)
        runs = args.runs
        if args.same_as:
            base = json.loads(args.same_as.read_text(encoding="utf-8"))
            session_ids = session_ids or base["session_ids"]
            runs = runs or base["runs_per_session"]
        if not session_ids:
            parser.error("--session か --same-as を指定する")
        path = asyncio.run(_run(session_ids, runs or 5, args.out))
        print(f"report: {path}")
    else:
        before = json.loads(args.before.read_text(encoding="utf-8"))
        after = json.loads(args.after.read_text(encoding="utf-8"))
        print(compare(before, after))


if __name__ == "__main__":
    main()
