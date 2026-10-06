from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from core.config import REVIEW_TIMEZONE

REVIEW_INTERVAL_DAYS = [1, 3, 7, 14, 30, 60]
ESTABLISHED_INTERVAL_DAYS = 30


def calculate_next_review(completed_reviews: int, now: datetime | None = None) -> datetime:
    index = min(completed_reviews, len(REVIEW_INTERVAL_DAYS) - 1)
    return (now or datetime.now(UTC)) + timedelta(days=REVIEW_INTERVAL_DAYS[index])


def is_early_review(next_review_at: datetime, now: datetime | None = None) -> bool:
    tz = ZoneInfo(REVIEW_TIMEZONE)
    return next_review_at.astimezone(tz).date() > (now or datetime.now(UTC)).astimezone(tz).date()


def is_established(review_count: int) -> bool:
    if review_count <= 0:
        return False
    last_interval = REVIEW_INTERVAL_DAYS[min(review_count - 1, len(REVIEW_INTERVAL_DAYS) - 1)]
    return last_interval >= ESTABLISHED_INTERVAL_DAYS
