import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.runner import InstanceResult
from evals.tools.capture import MAP_ROUTE
from graph.llm import RESPONSE_MODELS
from graph.prompts.map_question import MAP_PROMPT_FINGERPRINT
from graph.prompts.question import PROMPT_FINGERPRINT, PROMPT_VERSION


def next_rerun_id(source_trace_id: str, existing: set[str]) -> str:
    """`{元 id}-rerun{連番}` の空き番号を返す。採取セッションを重ねても既存 id を踏まない。"""
    index = 1
    while f"{source_trace_id}-rerun{index:02d}" in existing:
        index += 1
    return f"{source_trace_id}-rerun{index:02d}"


def _rerun_meta(base_meta: dict[str, Any]) -> dict[str, Any]:
    is_map = base_meta.get("route") == MAP_ROUTE
    meta: dict[str, Any] = {"model": RESPONSE_MODELS["learning-dialogue"].model}
    if not is_map:
        meta["prompt_version"] = PROMPT_VERSION
    meta["prompt_fingerprint"] = MAP_PROMPT_FINGERPRINT if is_map else PROMPT_FINGERPRINT
    meta["params"] = {"temperature": RESPONSE_MODELS["learning-dialogue"].temperature}
    if captured_by := base_meta.get("captured_by"):
        meta["captured_by"] = captured_by
    if is_map:
        meta["route"] = MAP_ROUTE
    return meta


def emit_jsonl(path: Path, results: list[InstanceResult], sources: dict[str, dict[str, Any]]) -> list[str]:
    """regression の生成を正本 jsonl へ追記する。input は元 instance のものを引き継ぐ。

    既存行は書き換えず追記だけする（近傍事例の採取が主目的で、annotate は人間が後から行う）。
    """
    existing = set(sources)
    written: list[str] = []
    with path.open("a", encoding="utf-8") as f:
        for result in results:
            base = sources[result.source_trace_id]
            for run in result.runs:
                if run.generation is None:
                    continue
                trace_id = next_rerun_id(result.source_trace_id, existing)
                # input は元レコードのものをそのまま引き継ぐ（生成後の値を書くと、この行を
                # 再度 regression にかけたとき coverage が二重に入る）。
                record = {
                    "id": trace_id,
                    "schema_version": base["schema_version"],
                    "source": "rerun",
                    "session": base["session"],
                    "dialogue_session_id": None,
                    "turn": base["turn"],
                    "captured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "meta": _rerun_meta(base["meta"]),
                    "input": {
                        "conversation_history": base["input"]["conversation_history"],
                        "graph_state": base["input"]["graph_state"],
                    },
                    "output": run.generation.output,
                    "turn_decision": run.generation.turn_decision(),
                    "pass": None,
                    "first_failure": None,
                    "note": f"regression 再実行（{result.source_trace_id} の入力を再利用）。未 annotate",
                    "annotated_at": None,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                existing.add(trace_id)
                written.append(trace_id)
    return written
