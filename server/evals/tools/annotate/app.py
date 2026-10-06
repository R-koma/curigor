"""annotate UI の HTTP 面（ローカル専用・認証なし）。

`create_app` をファクトリにしているのは、テストが tmp_path のデータセットへ TestClient を
張れるようにするため。
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from evals.rubric import RUBRIC_DIR
from evals.taxonomy import FAILURE_MODES
from evals.tools.annotate.map_view import map_view
from evals.tools.annotate.store import (
    DEFAULT_GOLDEN_DIR,
    DEFAULT_JSONL_PATH,
    Annotation,
    AnnotationError,
    Promotion,
    PromotionError,
    VerdictError,
    assertions_by_failure_mode,
    default_verified_by,
    deterministic_outcomes,
    golden_instances,
    load_records,
    promote_to_golden,
    save_annotation,
    update_verdicts,
)

_INDEX = Path(__file__).parent / "static" / "index.html"


class AnnotationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    verdict: bool | None = Field(default=None, alias="pass")
    first_failure: str | None = None
    note: str = ""


class PromotionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    failure_mode: str
    human_verdicts: dict[str, str]
    rationale: str
    verified_by: str


class VerdictsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    human_verdicts: dict[str, str]


def _summary(record: dict[str, Any], promoted_to: str | None) -> dict[str, Any]:
    return {
        "id": record["id"],
        "session": record["session"],
        "topic": record["input"]["graph_state"].get("topic"),
        "turn": record["turn"],
        "source": record["source"],
        "pass": record["pass"],
        "first_failure": record["first_failure"],
        "note": record["note"],
        "annotated_at": record["annotated_at"],
        "annotated": record["pass"] is not None,
        "promoted_to": promoted_to,
        "meta": record["meta"],
    }


def create_app(
    *,
    jsonl_path: Path = DEFAULT_JSONL_PATH,
    golden_dir: Path = DEFAULT_GOLDEN_DIR,
    rubric_dir: Path = RUBRIC_DIR,
) -> FastAPI:
    app = FastAPI(title="eval annotate", docs_url=None, redoc_url=None)

    def _find(trace_id: str) -> dict[str, Any]:
        for record in load_records(jsonl_path):
            if record["id"] == trace_id:
                return record
        raise HTTPException(status_code=404, detail=f"unknown trace id: {trace_id}")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_INDEX)

    @app.get("/api/records")
    def list_records() -> dict[str, Any]:
        promoted = golden_instances(golden_dir)
        summaries = [
            _summary(record, promoted[record["id"]].failure_mode if record["id"] in promoted else None)
            for record in load_records(jsonl_path)
        ]
        return {"records": sorted(summaries, key=lambda s: (s["session"], s["turn"], s["id"]))}

    @app.get("/api/records/{trace_id}")
    def get_record(trace_id: str) -> dict[str, Any]:
        record = _find(trace_id)
        promoted = golden_instances(golden_dir).get(trace_id)
        return {
            "record": _summary(record, promoted.failure_mode if promoted else None),
            "conversation_history": record["input"]["conversation_history"],
            "graph_state": record["input"]["graph_state"],
            "output": record["output"],
            "turn_decision": record.get("turn_decision"),
            "depth_map": map_view(record),
            "failure_modes": [{"key": key, "description": FAILURE_MODES[key]} for key in sorted(FAILURE_MODES)],
            "assertions": assertions_by_failure_mode(golden_dir, rubric_dir),
            "deterministic_outcomes": [
                asdict(o)
                for o in deterministic_outcomes(
                    record["output"], golden_dir, conversation_history=record["input"]["conversation_history"]
                )
            ],
            "default_verified_by": default_verified_by(golden_dir),
            "promoted_verdicts": promoted.human_verdicts if promoted else {},
        }

    @app.post("/api/records/{trace_id}/promote")
    def promote(trace_id: str, payload: PromotionPayload) -> dict[str, Any]:
        _find(trace_id)
        try:
            path = promote_to_golden(
                jsonl_path,
                golden_dir,
                trace_id,
                Promotion(
                    failure_mode=payload.failure_mode,
                    human_verdicts=payload.human_verdicts,
                    rationale=payload.rationale,
                    verified_by=payload.verified_by,
                ),
                rubric_dir=rubric_dir,
            )
        except PromotionError as exc:
            raise HTTPException(status_code=422, detail={"problems": exc.problems}) from exc
        record = _find(trace_id)
        promoted = golden_instances(golden_dir).get(trace_id)
        return {
            "record": _summary(record, promoted.failure_mode if promoted else None),
            "written_to": path.name,
            "next_step": "uv run pytest tests/unit/evals -q で写しの一致と両方向カバレッジを確認する",
        }

    @app.put("/api/records/{trace_id}/verdicts")
    def put_verdicts(trace_id: str, payload: VerdictsPayload) -> dict[str, Any]:
        _find(trace_id)
        try:
            path = update_verdicts(golden_dir, trace_id, payload.human_verdicts, rubric_dir=rubric_dir)
        except VerdictError as exc:
            raise HTTPException(status_code=422, detail={"problems": exc.problems}) from exc
        return {
            "written_to": path.name,
            "human_verdicts": golden_instances(golden_dir)[trace_id].human_verdicts,
            "next_step": "uv run pytest tests/unit/evals -q で両方向カバレッジを確認する",
        }

    @app.put("/api/records/{trace_id}/annotation")
    def put_annotation(trace_id: str, payload: AnnotationPayload) -> dict[str, Any]:
        _find(trace_id)
        annotation = Annotation(
            verdict=payload.verdict, first_failure=payload.first_failure, note=payload.note.strip()
        )
        try:
            updated = save_annotation(jsonl_path, trace_id, annotation, golden_dir=golden_dir)
        except AnnotationError as exc:
            raise HTTPException(status_code=422, detail={"problems": exc.problems}) from exc
        promoted = golden_instances(golden_dir).get(trace_id)
        return {"record": _summary(updated, promoted.failure_mode if promoted else None)}

    return app
