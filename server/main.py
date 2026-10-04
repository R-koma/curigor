import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import (
    dialogue_session,
    feedback,
    note,
    note_collection,
    note_revision,
    review_schedule,
    speech,
    transcription,
)
from api.websocket import chat
from core.database import close_pool, get_pool
from graph.builder import build_learning_graph
from graph.checkpointer import get_checkpointer
from observability.langfuse_tracing import init_tracing, shutdown_tracing
from observability.langfuse_tracing import is_enabled as is_tracing_enabled
from repositories import dialogue_session_repository

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("uvicorn").propagate = False

logger = logging.getLogger(__name__)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """未捕捉例外をログに残しつつ、スタックトレースを秘匿した 500 を返す。

    HTTPException / RequestValidationError は FastAPI 既定ハンドラに委ねる。
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_tracing()

    pool = await get_pool()
    async with pool.acquire() as conn:
        await dialogue_session_repository.reset_stuck_generations(conn)

    async with get_checkpointer() as checkpointer:
        await checkpointer.setup()
        app.state.graph = build_learning_graph(checkpointer)
        yield

    shutdown_tracing()
    await close_pool()


app = FastAPI(title="Curigor API", lifespan=lifespan)

app.add_exception_handler(Exception, unhandled_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(note.router)
app.include_router(note_revision.router)
app.include_router(note_collection.router)
app.include_router(feedback.router)
app.include_router(review_schedule.router)
app.include_router(dialogue_session.router)
app.include_router(transcription.router)
app.include_router(speech.router)
app.include_router(chat.router)


@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    """DB 到達性と Langfuse 送出の有無を返す。

    `tracing` は status に影響させない。キー未設定でもアプリは正常に動作するため、
    観測が無いことでヘルスチェックを落とすとデプロイやオートスケールを壊す。
    「本番なのに送出が無い」ことに気づくための可視化であり、可否判定ではない。
    """
    tracing = is_tracing_enabled()
    try:
        pool = await get_pool()
        row = await pool.fetchrow("SELECT 1 as check")
    except Exception as exc:  # noqa: BLE001 - DB 障害はステータスで表現し、例外で 500 にしない
        logger.warning("health check failed: %s", exc)
        return {"status": "error", "db": False, "tracing": tracing}
    if row is None:
        return {"status": "error", "db": False, "tracing": tracing}
    return {"status": "ok", "db": row["check"] == 1, "tracing": tracing}
