from datetime import datetime, timedelta

REVIEW_INTERVAL_DAYS = [1, 3, 7, 14, 30, 60]
ESTABLISHED_INTERVAL_DAYS = 30


def calculate_next_review(current_review_count: int) -> datetime:
    index = min(current_review_count, len(REVIEW_INTERVAL_DAYS) - 1)
    return datetime.now() + timedelta(days=REVIEW_INTERVAL_DAYS[index])


def is_established(review_count: int) -> bool:
    if review_count <= 0:
        return False
    last_interval = REVIEW_INTERVAL_DAYS[min(review_count - 1, len(REVIEW_INTERVAL_DAYS) - 1)]
    return last_interval >= ESTABLISHED_INTERVAL_DAYS
