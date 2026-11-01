import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from schemas.reflection import (
    DayReflection,
    ReflectionGroup,
    ReflectionSessionType,
    ReflectionTopic,
    WeekDayStatus,
    WeekReflection,
    WeekReflectionDay,
    WeekStruggle,
    WeekTopic,
)
from schemas.study_memo import StudyMemoQuestion

_GROUP_ORDER: tuple[ReflectionSessionType, ...] = ("learning", "explore", "review")
_REVIEW_NON_STRUGGLE = ("explained", "not_asked")


def week_start_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _struggles(row: dict[str, Any]) -> list[str]:
    if row["session_type"] == "explore":
        return []
    if row["session_type"] == "review":
        return [r["point"] for r in row.get("review_results") or [] if r.get("status") not in _REVIEW_NON_STRUGGLE]
    items = row.get("improvement_items")
    if items is not None:
        return [item.get("headline") or item["text"] for item in items]
    improvements = row.get("improvements")
    return [improvements] if improvements else []


def _questions(row: dict[str, Any]) -> list[StudyMemoQuestion]:
    if row["session_type"] != "explore":
        return []
    return [StudyMemoQuestion.model_validate(q) for q in row.get("questions") or []]


def _to_topic(row: dict[str, Any]) -> ReflectionTopic:
    source_id = row["memo_id"] if row["session_type"] == "explore" else row["note_id"]
    return ReflectionTopic(
        session_type=row["session_type"],
        source_id=source_id,
        topic=row["topic"],
        summary=row["summary"],
        struggles=_struggles(row),
        questions=_questions(row),
    )


def _merge_day_rows(rows: list[dict[str, Any]]) -> list[ReflectionTopic]:
    merged: dict[tuple[str, Any], tuple[datetime, ReflectionTopic]] = {}
    for row in rows:
        topic = _to_topic(row)
        key = (topic.session_type, topic.source_id)
        existing = merged.get(key)
        if existing is None or row["finished_at"] >= existing[0]:
            merged[key] = (row["finished_at"], topic)
    return [topic for _, topic in sorted(merged.values(), key=lambda item: item[0])]


def build_day(day: date, rows: list[dict[str, Any]]) -> DayReflection:
    topics = _merge_day_rows([r for r in rows if r["day"] == day])
    groups = [
        ReflectionGroup(session_type=t, topics=[x for x in topics if x.session_type == t])
        for t in _GROUP_ORDER
        if any(x.session_type == t for x in topics)
    ]
    return DayReflection(day=day, groups=groups)


def build_week(week_start: date, rows: list[dict[str, Any]]) -> WeekReflection:
    by_day: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_day[row["day"]].append(row)
    days: list[WeekReflectionDay] = []
    struggles: list[WeekStruggle] = []
    for day in sorted(by_day):
        topics = _merge_day_rows(by_day[day])
        days.append(
            WeekReflectionDay(day=day, topics=[WeekTopic(session_type=t.session_type, topic=t.topic) for t in topics])
        )
        for t in topics:
            struggles.extend(WeekStruggle(topic=t.topic, kind="struggle", text=s) for s in t.struggles)
            struggles.extend(
                WeekStruggle(topic=t.topic, kind="question", text=q.question, answer=q.answer) for q in t.questions
            )
    return WeekReflection(week_start=week_start, days=days, struggles=struggles)


def build_week_days(
    week_start: date, rows: list[dict[str, Any]], viewed_at: dict[date, datetime], today: date
) -> list[WeekDayStatus]:
    latest: dict[date, datetime] = {}
    for row in rows:
        day = row["day"]
        if day not in latest or row["finished_at"] > latest[day]:
            latest[day] = row["finished_at"]
    statuses: list[WeekDayStatus] = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        has_learning = day <= today and day in latest
        viewed = viewed_at.get(day)
        unread = has_learning and (viewed is None or latest[day] > viewed)
        statuses.append(WeekDayStatus(day=day, has_learning=has_learning, unread=unread))
    return statuses


def build_week_details(rows: list[dict[str, Any]]) -> list[DayReflection]:
    return [build_day(day, rows) for day in sorted({row["day"] for row in rows})]


def content_hash(days: list[DayReflection], label: str) -> str:
    payload = json.dumps([label, [d.model_dump(mode="json") for d in days]], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()
