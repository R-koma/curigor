import logging
import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from api.dependencies import CurrentUser
from core import config
from core.database import get_pool
from observability.langfuse_tracing import start_speech_trace
from repositories import dialogue_session_repository, speech_usage_repository
from schemas.speech import SpeechRequest
from speech import SpeechError, Synthesizer, get_synthesizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/speech", tags=["speech"])


@router.post("")
async def create_speech(
    body: SpeechRequest,
    current_user_id: CurrentUser,
    synthesizer: Annotated[Synthesizer, Depends(get_synthesizer)],
) -> StreamingResponse:
    text = body.text.strip()
    if not text or len(text) > config.MAX_SPEECH_CHARS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Text is empty or too long")

    pool = await get_pool()
    async with pool.acquire() as conn:
        session = await dialogue_session_repository.find_by_id(conn, body.dialogue_session_id, current_user_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        used = await speech_usage_repository.sum_today_by_user(conn, current_user_id, config.REVIEW_TIMEZONE)
    if used >= config.DAILY_SPEECH_CHAR_LIMIT:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Daily speech limit reached")

    trace = start_speech_trace(
        session_id=body.dialogue_session_id, user_id=current_user_id, model=synthesizer.model, characters=len(text)
    )
    started = time.monotonic()
    stream = synthesizer.stream(text, body.speed)
    try:
        first = await anext(stream, b"")
    except SpeechError as exc:
        logger.warning("Speech synthesis failed", exc_info=exc)
        trace.finish(0)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Speech synthesis failed") from exc
    except BaseException:
        await stream.aclose()
        trace.finish(0)
        raise
    trace.first_byte(round((time.monotonic() - started) * 1000))
    async with pool.acquire() as conn:
        await speech_usage_repository.insert(
            conn, current_user_id, body.dialogue_session_id, len(text), synthesizer.model
        )

    async def audio() -> AsyncIterator[bytes]:
        sent = 0
        try:
            if first:
                sent += len(first)
                yield first
            async for chunk in stream:
                sent += len(chunk)
                yield chunk
        except SpeechError as exc:
            logger.warning("Speech stream failed", exc_info=exc)
            raise
        finally:
            trace.finish(sent)
            await stream.aclose()

    async def close_stream() -> None:
        await stream.aclose()

    return StreamingResponse(audio(), media_type="application/octet-stream", background=BackgroundTask(close_stream))
