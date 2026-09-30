"""実セッション（DB + LangGraph チェックポイント）から eval 用 jsonl レコードを生成する。

手作業の転記では `topic` / `turn_count` / `covered_aspects` / `turn_analysis` /
`dialogue_session_id` が推測値や null で混入する。いずれも DB とチェックポイントに正確な値が
あるので機械的に引き、人間の仕事を `pass` / `first_failure` / `note` の annotate だけに縮める。

golden レコード（assertion・rationale）の作成は分析的判断を伴うため対象外。写しの生成は
`evals.eval --emit-instance` が担う。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import asyncpg
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from core.config import DATABASE_URL, REVIEW_TIMEZONE
from core.database import DBConnection
from graph.llm import llm
from graph.prompts.map_question import MAP_PROMPT_FINGERPRINT
from graph.prompts.question import PROMPT_FINGERPRINT, PROMPT_VERSION
from repositories import dialogue_message_image_repository, dialogue_message_repository

SCHEMA_VERSION = 3

# regression が「本番のターンを忠実に再現できる入力か」を判定するために読む印
CAPTURED_BY = "capture"

# order 1 = ユーザーのトピック、2 = learning_start の初期応答（聞き取りの最初の問いであり
# generate_question の eval 対象外）。対象は 4 以降のアシスタント応答。
_FIRST_DIALOGUE_ORDER = 4

MAP_ROUTE = "map"
MAP_SCHEMA_VERSION = 4

_FIRST_MAP_DIALOGUE_ORDER = 6

_DEFAULT_OUT = Path(__file__).resolve().parents[1] / "datasets" / "generate_questions.jsonl"

_FALLBACK_NOTE = (
    "capture: 生成直前のチェックポイントに対応付けできず "
    "covered_aspects / turn_count / turn_analysis / turn_decision を省略"
)

_SELECT_SESSION = """--sql
SELECT id, session_type, status, started_at, graph_version
FROM dialogue_sessions
"""

_LIST_SESSIONS = """--sql
SELECT
    s.id,
    s.status,
    s.started_at,
    (
        SELECT content
        FROM dialogue_messages
        WHERE dialogue_session_id = s.id AND role = 'user'
        ORDER BY message_order ASC
        LIMIT 1
    ) AS topic,
    (
        SELECT count(*)
        FROM dialogue_messages
        WHERE dialogue_session_id = s.id AND role = 'assistant' AND message_order >= $1
    ) AS target_turns
FROM dialogue_sessions s
WHERE s.session_type = 'learning'
ORDER BY s.started_at DESC
LIMIT $2
"""


@dataclass(frozen=True)
class TurnSnapshots:
    pre: dict[str, Any]
    post: dict[str, Any]


def _database_url() -> str:
    if DATABASE_URL is None:
        raise RuntimeError("DATABASE_URL is not set")
    return DATABASE_URL


def _message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            parts.append(str(block.get("text", "")))
    return "".join(parts)


def target_turns(
    messages: list[dict[str, Any]],
    message_ids_with_images: set[UUID] | None = None,
    first_order: int = _FIRST_DIALOGUE_ORDER,
) -> list[dict[str, Any]]:
    """エクスポート対象のアシスタント応答。

    直前のユーザーメッセージに画像が付くターンは除く。画像は jsonl に載せない方針なので、
    そのまま出すと「画像なしの入力」として再実行され、静かに別のターンを測ることになる。
    """
    with_images = message_ids_with_images or set()
    by_order = {m["message_order"]: m for m in messages}
    targets = []
    for message in messages:
        if message["role"] != "assistant" or message["message_order"] < first_order:
            continue
        previous = by_order.get(message["message_order"] - 1)
        if previous is not None and previous.get("id") in with_images:
            continue
        targets.append(message)
    return targets


def conversation_history(messages: list[dict[str, Any]], message_order: int) -> list[dict[str, str]]:
    """対象応答より前の全メッセージ。

    直近数件に切らない: `classify_user_intent` は全 human メッセージを走査して
    `substantive_prior` を判定するため、再実行の忠実度には全履歴が要る。
    """
    return [{"role": m["role"], "content": m["content"]} for m in messages if m["message_order"] < message_order]


def duplicate_user_message_warnings(messages: list[dict[str, Any]]) -> list[str]:
    """同一本文が連続するユーザーメッセージを知らせる。

    応答が返らないまま切断されたターンの再送で起きる（実セッションで観測）。写しとしては
    忠実だが eval の入力としてはノイズなので、annotate 前に気づけるようにする。
    """
    return [
        f"t{current['message_order']}: 直前のユーザーメッセージと同一本文（再送の可能性）"
        for previous, current in zip(messages, messages[1:], strict=False)
        if previous["role"] == "user" and current["role"] == "user" and previous["content"] == current["content"]
    ]


def find_turn_snapshots(snapshots: list[dict[str, Any]], index: int, output: str) -> TurnSnapshots | None:
    """対象応答のターンの、生成直前（入力）と生成後（決定内容）のチェックポイントを返す。

    `covered_aspects` / `turn_analysis` は応答と同じ super-step で書かれるので、
    ノードに渡された値は `pre`、そのターンが決めた値は `post` の側にある。

    同じメッセージ件数のスナップショットが複数回現れうる（メッセージ取り消しで state が縮む）
    ので、対象応答の本文一致で位置を固定してから直前の1件を採る。
    """
    pre: dict[str, Any] | None = None
    for values in snapshots:
        messages = values.get("messages") or []
        if len(messages) == index:
            pre = values
        elif len(messages) > index:
            candidate = messages[index]
            if getattr(candidate, "type", "") == "ai" and _message_text(candidate) == output:
                return TurnSnapshots(pre=pre, post=values) if pre is not None else None
    return None


def to_graph_state(values: dict[str, Any]) -> dict[str, Any]:
    graph_state: dict[str, Any] = {
        "topic": values["topic"],
        "learning_goal": values.get("learning_goal"),
        "focus_aspects": list(values.get("focus_aspects") or []),
        "covered_aspects": [dict(a) for a in values.get("covered_aspects") or []],
        "turn_count": values["turn_count"],
        "turn_analysis": dict(values["turn_analysis"]) if values.get("turn_analysis") else None,
    }
    if "wrap_up_offered" in values:
        graph_state["wrap_up_offered"] = bool(values["wrap_up_offered"])
    return graph_state


def to_static_graph_state(values: dict[str, Any], topic: str) -> dict[str, Any]:
    """対応付け失敗時のフォールバック。ターン固有のキーは省略する。

    値が無いこと（null）と取り漏らし（キー欠損）を区別できる状態を保つ。
    """
    return {
        "topic": values.get("topic") or topic,
        "learning_goal": values.get("learning_goal"),
        "focus_aspects": list(values.get("focus_aspects") or []),
    }


def to_map_graph_state(values: dict[str, Any]) -> dict[str, Any] | None:
    """地図に沿ったターンの生成直前の state。`depth_map` が無ければ None（旧経路のフォールバック）。"""
    if not values.get("depth_map"):
        return None
    return {
        "topic": values["topic"],
        "learning_goal": values.get("learning_goal"),
        "learning_source": values.get("learning_source"),
        "prior_knowledge": values.get("prior_knowledge"),
        "focus_aspects": list(values.get("focus_aspects") or []),
        "depth_map": deepcopy(values["depth_map"]),
        "map_covered": [dict(c) for c in values.get("map_covered") or []],
        "intake_message_count": values.get("intake_message_count", 0),
        "turn_count": values["turn_count"],
        "wrap_up_offered": bool(values.get("wrap_up_offered", False)),
        "turn_analysis": dict(values["turn_analysis"]) if values.get("turn_analysis") else None,
    }


def map_turn_decision_field(post: dict[str, Any]) -> dict[str, Any]:
    """地図に沿ったターンがプロンプトへ注入した決定値。観点が増えうるので merge 後の地図も持つ。"""
    decision = post.get("turn_analysis")
    if not decision:
        return {"turn_decision": None}
    return {
        "turn_decision": {
            **dict(decision),
            "depth_map": deepcopy(post["depth_map"]),
            "map_covered": [dict(c) for c in post.get("map_covered") or []],
        }
    }


def turn_decision_field(post: dict[str, Any]) -> dict[str, Any]:
    """そのターンがプロンプトへ注入した決定値（応答モード・焦点観点・merge 後のカバレッジ）。

    `input.graph_state` 側は生成直前の値なので、`turn_analysis` は「前のターンの決定」、
    `covered_aspects` は merge 前。プロンプトに入るのはどちらも生成後の値なので、
    決定を注入して再生成する用途（案A）はこのフィールドを読む。

    事前分析が走らなかったターンは `null`。この場合プロンプトの coverage は merge 前と
    同じなので `input.graph_state.covered_aspects` で足りる。
    `turn_analysis` を state に持たない時期のチェックポイントではキーごと省略する。
    """
    if "turn_analysis" not in post:
        return {}
    decision = post["turn_analysis"]
    if not decision:
        return {"turn_decision": None}
    return {
        "turn_decision": {
            **dict(decision),
            "covered_aspects": [dict(a) for a in post.get("covered_aspects") or []],
        }
    }


def session_label(session_id: UUID, started_at: datetime) -> str:
    date = started_at.astimezone(ZoneInfo(REVIEW_TIMEZONE)).date().isoformat()
    return f"{date}-{str(session_id)[:8]}"


def build_record(
    *,
    session_id: UUID,
    started_at: datetime,
    message: dict[str, Any],
    history: list[dict[str, str]],
    graph_state: dict[str, Any],
    decision: dict[str, Any],
    note: str = "",
    route: str | None = None,
) -> dict[str, Any]:
    label = session_label(session_id, started_at)
    order = message["message_order"]
    is_map = route == MAP_ROUTE
    meta: dict[str, Any] = {"model": llm.model_name}
    if not is_map:
        meta["prompt_version"] = PROMPT_VERSION
    meta["prompt_fingerprint"] = MAP_PROMPT_FINGERPRINT if is_map else PROMPT_FINGERPRINT
    meta["params"] = {"temperature": llm.temperature}
    meta["captured_by"] = CAPTURED_BY
    if is_map:
        meta["route"] = MAP_ROUTE
    return {
        "id": f"{label}__t{order}",
        "schema_version": MAP_SCHEMA_VERSION if is_map else SCHEMA_VERSION,
        "source": "real",
        "session": label,
        "dialogue_session_id": str(session_id),
        "turn": order,
        "captured_at": message["created_at"].astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "meta": meta,
        "input": {"conversation_history": history, "graph_state": graph_state},
        "output": message["content"],
        **decision,
        "pass": None,
        "first_failure": None,
        "note": note,
        "annotated_at": None,
    }


def build_records(
    session_id: UUID,
    started_at: datetime,
    messages: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
    message_ids_with_images: set[UUID] | None = None,
    *,
    route: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    # chat.py は learning セッションの message_order 1 に topic 文字列そのものを保存するため、
    # チェックポイントを失った場合の topic はここから復元できる。
    topic = messages[0]["content"] if messages else ""
    latest = snapshots[-1] if snapshots else {}
    is_map = route == MAP_ROUTE
    first_order = _FIRST_MAP_DIALOGUE_ORDER if is_map else _FIRST_DIALOGUE_ORDER

    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    warnings.extend(duplicate_user_message_warnings(messages))
    targets = target_turns(messages, message_ids_with_images, first_order)
    kept = {t["message_order"] for t in targets}
    warnings.extend(
        f"t{m['message_order']}: 直前のユーザーメッセージに画像があるためスキップした"
        for m in target_turns(messages, first_order=first_order)
        if m["message_order"] not in kept
    )
    for message in targets:
        order = message["message_order"]
        turn = find_turn_snapshots(snapshots, order - 1, message["content"])
        if is_map:
            map_state = to_map_graph_state(turn.pre) if turn is not None else None
            if turn is None or map_state is None:
                warnings.append(f"t{order}: 地図に沿ったターンとして対応付けできなかったのでスキップした")
                continue
            graph_state, decision, note = map_state, map_turn_decision_field(turn.post), ""
        elif turn is None:
            warnings.append(f"t{order}: 生成直前のチェックポイントに対応付けできなかった")
            graph_state, decision, note = to_static_graph_state(latest, topic), {}, _FALLBACK_NOTE
        else:
            graph_state, decision, note = to_graph_state(turn.pre), turn_decision_field(turn.post), ""
        records.append(
            build_record(
                session_id=session_id,
                started_at=started_at,
                message=message,
                history=conversation_history(messages, order),
                graph_state=graph_state,
                decision=decision,
                note=note,
                route=route,
            )
        )
    return records, warnings


def existing_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as f:
        return {json.loads(line)["id"] for line in f if line.strip()}


def split_unseen(path: Path, records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """既存 jsonl に無いレコードと、id 重複でスキップした件数を返す（再実行安全性）。"""
    known = existing_ids(path)
    unseen = [r for r in records if r["id"] not in known]
    return unseen, len(records) - len(unseen)


def append_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


async def fetch_session(conn: DBConnection, session_id: UUID) -> dict[str, Any]:
    record = await conn.fetchrow(_SELECT_SESSION + "WHERE id = $1", str(session_id))
    if record is None:
        raise LookupError(f"dialogue session not found: {session_id}")
    return dict(record)


async def latest_learning_session(conn: DBConnection) -> dict[str, Any]:
    record = await conn.fetchrow(_SELECT_SESSION + "WHERE session_type = 'learning' ORDER BY started_at DESC LIMIT 1")
    if record is None:
        raise LookupError("learning セッションが 1 件も無い")
    return dict(record)


async def list_recent_sessions(conn: DBConnection, limit: int) -> list[dict[str, Any]]:
    records = await conn.fetch(_LIST_SESSIONS, _FIRST_DIALOGUE_ORDER, limit)
    return [dict(r) for r in records]


async def load_snapshots(checkpointer: AsyncPostgresSaver, session_id: UUID) -> list[dict[str, Any]]:
    """チェックポイント履歴を時系列昇順の channel_values 列にする（alist は新しい順）。"""
    config: RunnableConfig = {"configurable": {"thread_id": str(session_id)}}
    tuples = [t async for t in checkpointer.alist(config)]
    return [t.checkpoint["channel_values"] for t in reversed(tuples)]


def is_map_flow_session(snapshots: list[dict[str, Any]]) -> bool:
    return any("intake_complete" in values for values in snapshots)


async def collect(
    conn: DBConnection, checkpointer: AsyncPostgresSaver, session: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    if session["session_type"] != "learning":
        raise ValueError(f"learning セッションではない: session_type={session['session_type']}")
    messages = await dialogue_message_repository.find_by_session_id(conn, session["id"])
    snapshots = await load_snapshots(checkpointer, session["id"])
    images = await dialogue_message_image_repository.find_by_session_id(conn, session["id"])
    return build_records(
        session["id"],
        session["started_at"],
        messages,
        snapshots,
        {img["dialogue_message_id"] for img in images},
        route=MAP_ROUTE if is_map_flow_session(snapshots) else None,
    )


def captured_session_ids(path: Path) -> set[str]:
    """正本 jsonl に既に入っているセッション id。取り漏らしを --list で見えるようにする。"""
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as f:
        ids = {json.loads(line).get("dialogue_session_id") for line in f if line.strip()}
    return {i for i in ids if i}


def print_sessions(sessions: list[dict[str, Any]], captured: set[str]) -> None:
    for session in sessions:
        started = session["started_at"].astimezone(ZoneInfo(REVIEW_TIMEZONE)).strftime("%Y-%m-%d %H:%M")
        topic = (session["topic"] or "")[:30]
        mark = "captured" if str(session["id"]) in captured else "--------"
        print(
            f"{session['id']}  {started}  {session['status']:<12} turns={session['target_turns']:<3} {mark}  {topic}"
        )


async def run(args: argparse.Namespace, url: str) -> int:
    conn = await asyncpg.connect(url)
    try:
        if args.list:
            print_sessions(await list_recent_sessions(conn, args.limit), captured_session_ids(args.out))
            return 0
        session = await (latest_learning_session(conn) if args.latest else fetch_session(conn, args.session_id))
        async with AsyncPostgresSaver.from_conn_string(url) as checkpointer:
            records, warnings = await collect(conn, checkpointer, session)
    except (LookupError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        await conn.close()

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if not records:
        print(f"対象ターン（地図に沿った応答、または旧経路の応答）が無い: {session['id']}", file=sys.stderr)
        return 1

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
    if new:
        print("golden の写しは `uv run python -m evals.eval --emit-instance <id>` で生成する")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="evals.tools.capture", description="実セッションから eval 用 jsonl レコードを生成する"
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--latest", action="store_true", help="直近の learning セッションを対象にする")
    target.add_argument("--session-id", type=UUID, default=None, help="対象セッションの UUID")
    target.add_argument("--list", action="store_true", help="直近の learning セッション一覧を表示して終了")
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT, help="追記先の jsonl")
    parser.add_argument("--dry-run", action="store_true", help="追記せず生成レコードを表示する")
    parser.add_argument("--limit", type=int, default=10, help="--list で表示する件数")
    return parser.parse_args(argv)


def main() -> None:
    raise SystemExit(asyncio.run(run(parse_args(), _database_url())))


if __name__ == "__main__":
    main()
