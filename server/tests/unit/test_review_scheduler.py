from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from services.review_scheduler import calculate_next_review, is_early_review, is_established

INTERVALS = [1, 3, 7, 14, 30, 60]
FROZEN_TIME = "2026-03-26 12:00:00"
BASE_DT = datetime(2026, 3, 26, 12, tzinfo=UTC)


@freeze_time(FROZEN_TIME)
class TestCalculateNextReview:
    @pytest.mark.parametrize(
        ("completed_reviews", "days"),
        [(i, d) for i, d in enumerate(INTERVALS)],
        ids=[f"interval-{d}d" for d in INTERVALS],
    )
    def test_fixed_intervals(self, completed_reviews: int, days: int) -> None:
        assert calculate_next_review(completed_reviews) == BASE_DT + timedelta(days=days)

    def test_clamp_at_max(self) -> None:
        assert calculate_next_review(99) == BASE_DT + timedelta(days=60)

    def test_returns_aware_datetime(self) -> None:
        assert calculate_next_review(0).tzinfo is not None

    def test_first_review_after_learning_waits_three_days(self) -> None:
        after_learning = calculate_next_review(0)
        after_first_review = calculate_next_review(1)
        assert after_learning == BASE_DT + timedelta(days=1)
        assert after_first_review == BASE_DT + timedelta(days=3)


class TestIsEarlyReview:
    # REVIEW_TIMEZONE の既定は Asia/Tokyo（UTC+9）
    NOW = datetime(2026, 3, 26, 14, 0, tzinfo=UTC)  # 3/26 23:00 JST

    @pytest.mark.parametrize(
        ("next_review_at", "expected"),
        [
            (datetime(2026, 3, 25, 0, 0, tzinfo=UTC), False),
            (datetime(2026, 3, 26, 14, 30, tzinfo=UTC), False),
            (datetime(2026, 3, 26, 15, 0, tzinfo=UTC), True),
            (datetime(2026, 3, 30, 0, 0, tzinfo=UTC), True),
        ],
        ids=["overdue", "later-today", "tomorrow-00h-jst", "days-ahead"],
    )
    def test_compares_calendar_days_in_review_timezone(self, next_review_at: datetime, expected: bool) -> None:
        assert is_early_review(next_review_at, now=self.NOW) is expected


class TestIsEstablished:
    @pytest.mark.parametrize(("review_count", "expected"), [(0, False), (1, False), (4, False), (5, True), (9, True)])
    def test_established_once_the_last_interval_reaches_30_days(self, review_count: int, expected: bool) -> None:
        assert is_established(review_count) is expected
