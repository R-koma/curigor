from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response

from evals.transcription import load_items

_STATIC = Path(__file__).parent / "static"
_MAX_BYTES = 5 * 1024 * 1024
_MEDIA_TYPES = {"wav": "audio/wav", "webm": "audio/webm"}

AudioFormat = Literal["wav", "webm"]


def create_app(dataset: Path, audio_dir: Path) -> FastAPI:
    items = {item.id: item for item in load_items(dataset)}
    app = FastAPI()

    def audio_path(item_id: str, audio_format: AudioFormat) -> Path:
        if item_id not in items:
            raise HTTPException(status_code=404, detail="unknown item")
        return audio_dir / f"{item_id}.{audio_format}"

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_STATIC / "index.html")

    @app.get("/api/items")
    def list_items() -> list[dict[str, Any]]:
        return [
            {
                "id": item.id,
                "topic": item.topic,
                "category": item.category,
                "text": item.text,
                "recorded": audio_path(item.id, "wav").exists() and audio_path(item.id, "webm").exists(),
            }
            for item in items.values()
        ]

    @app.put("/api/items/{item_id}/audio/{audio_format}", status_code=204)
    async def save_audio(item_id: str, audio_format: AudioFormat, request: Request) -> Response:
        path = audio_path(item_id, audio_format)
        body = await request.body()
        if not body or len(body) > _MAX_BYTES:
            raise HTTPException(status_code=413, detail="empty or too large")
        path.write_bytes(body)
        return Response(status_code=204)

    @app.get("/api/items/{item_id}/audio/{audio_format}")
    def get_audio(item_id: str, audio_format: AudioFormat) -> FileResponse:
        path = audio_path(item_id, audio_format)
        if not path.exists():
            raise HTTPException(status_code=404, detail="not recorded")
        return FileResponse(path, media_type=_MEDIA_TYPES[audio_format])

    return app
