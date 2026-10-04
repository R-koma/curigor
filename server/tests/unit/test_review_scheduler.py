from datetime import datetime, timedelta

import pytest
from freezegun import freeze_time

from services.review_scheduler import calculate_next_review, is_established

INTERVALS = [1, 3, 7, 14, 30, 60]
FROZEN_TIME = "2026-03-26 12:00:00"
BASE_DT = datetime(2026, 3, 26, 12)


@freeze_time(FROZEN_TIME)
class TestCalculateNextReview:
    """calculate_next_review のユニットテスト"""

    @pytest.mark.parametrize(
        ("review_count", "days"),
        [(i, d) for i, d in enumerate(INTERVALS)],
        ids=[f"interval-{d}d" for d in INTERVALS],
    )
    def test_fixed_intervals(self, review_count: int, days: int) -> None:
        """review_count に対応する固定インターバルを検証"""
        result = calculate_next_review(current_review_count=review_count)
        assert result == BASE_DT + timedelta(days=days)

    def test_clamp_at_max(self) -> None:
        """review_count が最大インデックスを超えた場合、60日後にクランプされる"""
        result = calculate_next_review(current_review_count=99)
        assert result == BASE_DT + timedelta(days=60)


class TestIsEstablished:
    @pytest.mark.parametrize(("review_count", "expected"), [(0, False), (1, False), (4, False), (5, True), (9, True)])
    def test_established_once_the_last_interval_reaches_30_days(self, review_count: int, expected: bool) -> None:
        assert is_established(review_count) is expected
