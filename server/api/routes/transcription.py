import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from api.dependencies import CurrentUser
from core import config
from core.audio_signature import detect_audio_mime
from core.database import get_pool
from observability.langfuse_tracing import traced_transcription
from repositories import dialogue_session_repository, transcription_usage_repository
from schemas.transcription import TranscriptionResponse
from transcription import Transcriber, TranscriptionError, get_transcriber

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/transcriptions", tags=["transcriptions"])


def _base_mime_type(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


@router.post("", response_model=TranscriptionResponse)
async def create_transcription(
    current_user_id: CurrentUser,
    transcriber: Annotated[Transcriber, Depends(get_transcriber)],
    audio: Annotated[UploadFile, File()],
    dialogue_session_id: Annotated[UUID | None, Form()] = None,
) -> TranscriptionResponse:
    pool = await get_pool()
    if dialogue_session_id is not None:
        async with pool.acquire() as conn:
            session = await dialogue_session_repository.find_by_id(conn, dialogue_session_id, current_user_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    data = await audio.read(config.MAX_AUDIO_BYTES + 1)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audio is empty")
    if len(data) > config.MAX_AUDIO_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Audio is too large")
    mime_type = _base_mime_type(audio.content_type)
    if mime_type not in config.ALLOWED_AUDIO_MIME_TYPES or detect_audio_mime(data) != mime_type:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported audio format")

    async with pool.acquire() as conn:
        used = await transcription_usage_repository.count_today_by_user(conn, current_user_id, config.REVIEW_TIMEZONE)
    if used >= config.DAILY_TRANSCRIPTION_LIMIT:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Daily transcription limit reached")

    async with traced_transcription(
        session_id=dialogue_session_id, user_id=current_user_id, model=transcriber.model, audio_bytes=len(data)
    ) as trace:
        try:
            text = await transcriber.transcribe(data, mime_type)
        except TranscriptionError as exc:
            logger.warning("Transcription failed", exc_info=exc)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Transcription failed") from exc
        trace.set_output(text)

    async with pool.acquire() as conn:
        await transcription_usage_repository.insert(
            conn, current_user_id, dialogue_session_id, len(data), transcriber.model
        )
    return TranscriptionResponse(text=text)
