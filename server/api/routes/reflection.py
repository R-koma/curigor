from datetime import date, datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse

from api.dependencies import DB, ConsentedUser, CurrentUser
from api.errors import ApiError, ErrorCode
from api.routes.speech import reserve_speech, stream_reserved_speech
from core import config
from core.database import get_pool
from repositories import reflection_repository
from schemas.reflection import (
    DayReflection,
    ReflectionQuizResponse,
    ReflectionScriptResponse,
    ReflectionSpeechRequest,
    WeekDaysResponse,
    WeekReflection,
)
from services import reflection as reflection_service
from services import reflection_generation
from speech import Synthesizer, get_synthesizer

router = APIRouter(prefix="/api/reflections", tags=["reflections"])


@router.get("/weeks/{week_start}/days", response_model=WeekDaysResponse)
async def get_week_days(week_start: date, current_user_id: CurrentUser, db: DB) -> WeekDaysResponse:
    start = reflection_service.week_start_of(week_start)
    end = start + timedelta(days=7)
    rows = await reflection_repository.find_items_in_range(db, current_user_id, start, end, config.REVIEW_TIMEZONE)
    viewed_at = await reflection_repository.find_viewed_at(db, current_user_id, start, end)
    today = datetime.now(ZoneInfo(config.REVIEW_TIMEZONE)).date()
    return WeekDaysResponse(days=reflection_service.build_week_days(start, rows, viewed_at, today))


@router.get("/weeks/{week_start}", response_model=WeekReflection)
async def get_week(week_start: date, current_user_id: CurrentUser, db: DB) -> WeekReflection:
    start = reflection_service.week_start_of(week_start)
    rows = await reflection_repository.find_items_in_range(
        db, current_user_id, start, start + timedelta(days=7), config.REVIEW_TIMEZONE
    )
    return reflection_service.build_week(start, rows)


@router.get("/days/{day}", response_model=DayReflection)
async def get_day(day: date, current_user_id: CurrentUser, db: DB) -> DayReflection:
    rows = await reflection_repository.find_items_in_range(
        db, current_user_id, day, day + timedelta(days=1), config.REVIEW_TIMEZONE
    )
    return reflection_service.build_day(day, rows)


@router.put("/days/{day}/view", status_code=status.HTTP_204_NO_CONTENT)
async def mark_day_viewed(day: date, current_user_id: CurrentUser, db: DB) -> Response:
    await reflection_repository.mark_viewed(db, current_user_id, day)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _reflection_api_error(exc: Exception) -> ApiError:
    if isinstance(exc, reflection_generation.ReflectionEmptyError):
        return ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.REFLECTION_EMPTY, "Nothing to reflect on")
    if isinstance(exc, reflection_generation.ReflectionLimitError):
        return ApiError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            ErrorCode.DAILY_REFLECTION_LIMIT_REACHED,
            "Daily reflection limit reached",
        )
    return ApiError(
        status.HTTP_502_BAD_GATEWAY, ErrorCode.REFLECTION_GENERATION_FAILED, "Reflection generation failed"
    )


_GENERATION_ERRORS = (
    reflection_generation.ReflectionEmptyError,
    reflection_generation.ReflectionLimitError,
    reflection_generation.ReflectionGenerationError,
)


@router.post("/{period}/{start}/script", response_model=ReflectionScriptResponse)
async def create_script(
    period: Literal["day", "week"], start: date, current_user_id: ConsentedUser
) -> ReflectionScriptResponse:
    try:
        sentences = await reflection_generation.get_or_create_script(current_user_id, period, start)
    except _GENERATION_ERRORS as exc:
        raise _reflection_api_error(exc) from exc
    return ReflectionScriptResponse(sentences=sentences)


@router.post("/{period}/{start}/quiz", response_model=ReflectionQuizResponse)
async def create_quiz(
    period: Literal["day", "week"], start: date, current_user_id: ConsentedUser
) -> ReflectionQuizResponse:
    try:
        questions = await reflection_generation.get_or_create_quiz(current_user_id, period, start)
    except _GENERATION_ERRORS as exc:
        raise _reflection_api_error(exc) from exc
    return ReflectionQuizResponse(questions=questions)


@router.post("/speech")
async def create_reflection_speech(
    body: ReflectionSpeechRequest,
    current_user_id: ConsentedUser,
    synthesizer: Annotated[Synthesizer, Depends(get_synthesizer)],
) -> StreamingResponse:
    text = body.text.strip()
    if not text or len(text) > config.MAX_SPEECH_CHARS:
        raise ApiError(status.HTTP_400_BAD_REQUEST, ErrorCode.SPEECH_TEXT_INVALID, "Text is empty or too long")

    pool = await get_pool()
    async with pool.acquire() as conn:
        usage_id = await reserve_speech(conn, current_user_id, None, text, synthesizer)

    return await stream_reserved_speech(
        usage_id=usage_id,
        user_id=current_user_id,
        session_id=None,
        text=text,
        speed=body.speed,
        synthesizer=synthesizer,
    )
