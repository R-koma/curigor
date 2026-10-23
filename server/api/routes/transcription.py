import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from api.dependencies import ConsentedUser
from api.errors import ApiError, ErrorCode
from core import config
from core.audio_signature import detect_audio_mime, wav_duration_seconds
from core.database import get_pool
from observability.langfuse_tracing import traced_transcription
from repositories import dialogue_session_repository, transcription_usage_repository
from schemas.transcription import TranscriptFormatRequest, TranscriptFormatResponse, TranscriptionResponse
from services.transcript_format import TranscriptFormatError, format_transcript
from services.transcription_keywords import fallback_keywords
from transcription import Transcriber, TranscriptionError, get_transcriber

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/transcriptions", tags=["transcriptions"])


def _base_mime_type(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def _audio_seconds(data: bytes, mime_type: str) -> float | None:
    if mime_type == "audio/wav":
        return wav_duration_seconds(data)
    return len(data) / config.RECORDED_AUDIO_BYTES_PER_SECOND


async def _cancel_reservation(usage_id: UUID) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await transcription_usage_repository.cancel(conn, usage_id)


@router.post("", response_model=TranscriptionResponse)
async def create_transcription(
    current_user_id: ConsentedUser,
    transcriber: Annotated[Transcriber, Depends(get_transcriber)],
    audio: Annotated[UploadFile, File()],
    dialogue_session_id: Annotated[UUID | None, Form()] = None,
    prompt: Annotated[str | None, Form(max_length=config.MAX_TRANSCRIPTION_PROMPT_CHARS)] = None,
) -> TranscriptionResponse:
    pool = await get_pool()
    keywords: list[str] | None = None
    if dialogue_session_id is not None:
        async with pool.acquire() as conn:
            session = await dialogue_session_repository.find_by_id(conn, dialogue_session_id, current_user_id)
            if session:
                keywords, _ = await dialogue_session_repository.find_transcription_keywords(
                    conn, dialogue_session_id, current_user_id
                )
        if not session:
            raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.SESSION_NOT_FOUND, "Session not found")
        keywords = keywords or fallback_keywords(session["topic"])

    data = await audio.read(config.MAX_AUDIO_BYTES + 1)
    if not data:
        raise ApiError(status.HTTP_400_BAD_REQUEST, ErrorCode.AUDIO_EMPTY, "Audio is empty")
    if len(data) > config.MAX_AUDIO_BYTES:
        raise ApiError(status.HTTP_413_CONTENT_TOO_LARGE, ErrorCode.AUDIO_TOO_LARGE, "Audio is too large")
    mime_type = _base_mime_type(audio.content_type)
    if mime_type not in config.ALLOWED_AUDIO_MIME_TYPES or detect_audio_mime(data) != mime_type:
        raise ApiError(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, ErrorCode.UNSUPPORTED_AUDIO_FORMAT, "Unsupported audio format"
        )
    seconds = _audio_seconds(data, mime_type)
    if seconds is None:
        raise ApiError(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, ErrorCode.UNSUPPORTED_AUDIO_FORMAT, "Unsupported audio format"
        )

    async with pool.acquire() as conn:
        usage_id = await transcription_usage_repository.reserve(
            conn,
            current_user_id,
            dialogue_session_id,
            len(data),
            seconds,
            transcriber.model,
            config.REVIEW_TIMEZONE,
            config.DAILY_TRANSCRIPTION_SECONDS,
        )
    if usage_id is None:
        raise ApiError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            ErrorCode.DAILY_TRANSCRIPTION_LIMIT_REACHED,
            "Daily transcription limit reached",
        )

    async with traced_transcription(
        session_id=dialogue_session_id, user_id=current_user_id, model=transcriber.model, audio_bytes=len(data)
    ) as trace:
        try:
            text = await transcriber.transcribe(data, mime_type, prompt, keywords)
        except TranscriptionError as exc:
            logger.warning("Transcription failed", exc_info=exc)
            await _cancel_reservation(usage_id)
            raise ApiError(
                status.HTTP_502_BAD_GATEWAY, ErrorCode.TRANSCRIPTION_FAILED, "Transcription failed"
            ) from exc
        except BaseException:
            await _cancel_reservation(usage_id)
            raise
        trace.set_output(text)

    return TranscriptionResponse(text=text)


@router.post("/format", response_model=TranscriptFormatResponse)
async def format_transcription(
    body: TranscriptFormatRequest, current_user_id: ConsentedUser
) -> TranscriptFormatResponse:
    text = body.text.strip()
    if not text or len(text) > config.MAX_TRANSCRIPT_FORMAT_CHARS:
        raise ApiError(status.HTTP_400_BAD_REQUEST, ErrorCode.TRANSCRIPT_TEXT_INVALID, "Text is empty or too long")

    pool = await get_pool()
    async with pool.acquire() as conn:
        session = await dialogue_session_repository.find_by_id(conn, body.dialogue_session_id, current_user_id)
    if not session:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.SESSION_NOT_FOUND, "Session not found")

    try:
        formatted = await format_transcript(text, session_id=body.dialogue_session_id, user_id=current_user_id)
    except TranscriptFormatError as exc:
        logger.warning("Transcript formatting failed", exc_info=exc)
        raise ApiError(
            status.HTTP_502_BAD_GATEWAY, ErrorCode.TRANSCRIPT_FORMAT_FAILED, "Transcript formatting failed"
        ) from exc
    return TranscriptFormatResponse(text=formatted)
