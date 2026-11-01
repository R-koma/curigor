from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Response, status

from api.dependencies import DB, CurrentUser
from core import config
from repositories import reflection_repository
from schemas.reflection import DayReflection, WeekDaysResponse
from services import reflection as reflection_service

router = APIRouter(prefix="/api/reflections", tags=["reflections"])


@router.get("/weeks/{week_start}/days", response_model=WeekDaysResponse)
async def get_week_days(week_start: date, current_user_id: CurrentUser, db: DB) -> WeekDaysResponse:
    start = reflection_service.week_start_of(week_start)
    end = start + timedelta(days=7)
    rows = await reflection_repository.find_items_in_range(db, current_user_id, start, end, config.REVIEW_TIMEZONE)
    viewed_at = await reflection_repository.find_viewed_at(db, current_user_id, start, end)
    today = datetime.now(ZoneInfo(config.REVIEW_TIMEZONE)).date()
    return WeekDaysResponse(days=reflection_service.build_week_days(start, rows, viewed_at, today))


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
