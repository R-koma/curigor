from datetime import UTC, datetime, timedelta, timezone, tzinfo

from hypothesis import given
from hypothesis import strategies as st

from services.review_scheduler import REVIEW_INTERVAL_DAYS, calculate_next_review, is_early_review, is_established

# REVIEW_TIMEZONE の既定 Asia/Tokyo は 1951 年以降 DST がなく UTC+9 固定
JST = timezone(timedelta(hours=9))

aware_datetimes = st.datetimes(
    min_value=datetime(1990, 1, 1),
    max_value=datetime(2200, 1, 1),
    timezones=st.timezones(),
)
completed_reviews = st.integers(min_value=0, max_value=10**6)


@given(now=aware_datetimes, count=completed_reviews)
def test_next_review_is_after_now(now: datetime, count: int) -> None:
    assert calculate_next_review(count, now) > now


@given(now=aware_datetimes, count=completed_reviews)
def test_interval_never_shrinks_as_reviews_increase(now: datetime, count: int) -> None:
    assert calculate_next_review(count + 1, now) >= calculate_next_review(count, now)


@given(now=aware_datetimes, count=st.integers(min_value=len(REVIEW_INTERVAL_DAYS) - 1, max_value=10**6))
def test_interval_stays_at_last_value_after_all_intervals(now: datetime, count: int) -> None:
    assert calculate_next_review(count, now) - now == timedelta(days=REVIEW_INTERVAL_DAYS[-1])


@given(count=st.integers(min_value=-(10**6), max_value=10**6), extra=st.integers(min_value=0, max_value=10**6))
def test_is_established_is_monotonic(count: int, extra: int) -> None:
    if is_established(count):
        assert is_established(count + extra)


@given(now=aware_datetimes)
def test_review_at_now_is_never_early(now: datetime) -> None:
    assert is_early_review(now, now) is False


@given(next_review_at=aware_datetimes, now=aware_datetimes)
def test_is_early_review_matches_calendar_date_in_review_timezone(next_review_at: datetime, now: datetime) -> None:
    expected = next_review_at.astimezone(UTC).astimezone(JST).date() > now.astimezone(UTC).astimezone(JST).date()
    assert is_early_review(next_review_at, now) is expected


@given(
    next_review_at=aware_datetimes,
    now=aware_datetimes,
    tz_a=st.timezones(),
    tz_b=st.timezones(),
)
def test_is_early_review_ignores_input_timezone(
    next_review_at: datetime, now: datetime, tz_a: tzinfo, tz_b: tzinfo
) -> None:
    assert is_early_review(next_review_at.astimezone(tz_a), now.astimezone(tz_b)) is is_early_review(
        next_review_at, now
    )
