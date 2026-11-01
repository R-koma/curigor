from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from services.reflection import build_day, build_week, build_week_days, build_week_details, content_hash, week_start_of

DAY = date(2026, 11, 2)
T0 = datetime(2026, 11, 2, 1, 0, tzinfo=UTC)


def _row(session_type: str = "learning", *, minutes: int = 0, source: UUID | None = None, **kw: Any) -> dict[str, Any]:
    source = source or uuid4()
    row: dict[str, Any] = {
        "session_id": uuid4(),
        "session_type": session_type,
        "finished_at": T0 + timedelta(minutes=minutes),
        "day": DAY,
        "note_id": None if session_type == "explore" else source,
        "memo_id": source if session_type == "explore" else None,
        "topic": "T",
        "summary": "S",
        "improvement_items": None,
        "improvements": None,
        "review_results": None,
        "questions": None,
    }
    row.update(kw)
    return row


def test_groups_in_order_learning_explore_review() -> None:
    rows = [_row("review"), _row("explore"), _row("learning")]
    result = build_day(DAY, rows)
    assert [g.session_type for g in result.groups] == ["learning", "explore", "review"]


def test_merges_same_type_same_source_using_last_struggles() -> None:
    note = uuid4()
    rows = [
        _row(source=note, minutes=0, improvement_items=[{"text": "old"}]),
        _row(source=note, minutes=10, improvement_items=[{"text": "new"}]),
    ]
    topics = build_day(DAY, rows).groups[0].topics
    assert len(topics) == 1
    assert topics[0].struggles == ["new"]


def test_same_note_learning_and_review_stay_separate() -> None:
    note = uuid4()
    result = build_day(DAY, [_row("learning", source=note), _row("review", source=note, minutes=5)])
    assert [g.session_type for g in result.groups] == ["learning", "review"]


def test_learning_struggles_use_headline_then_text() -> None:
    row = _row(improvement_items=[{"headline": "H", "text": "T"}, {"text": "T2"}])
    assert build_day(DAY, [row]).groups[0].topics[0].struggles == ["H", "T2"]


def test_learning_falls_back_to_improvements_string() -> None:
    old = build_day(DAY, [_row(improvements="古い改善点")]).groups[0].topics[0]
    empty = build_day(DAY, [_row(improvements="")]).groups[0].topics[0]
    assert old.struggles == ["古い改善点"]
    assert empty.struggles == []


def test_review_struggles_exclude_explained_and_not_asked() -> None:
    results = [
        {"point": "a", "status": "explained"},
        {"point": "b", "status": "not_asked"},
        {"point": "c", "status": "not_explained"},
        {"point": "d", "status": "explained_with_hint"},
    ]
    topic = build_day(DAY, [_row("review", review_results=results)]).groups[0].topics[0]
    assert topic.struggles == ["c", "d"]


def test_explore_questions_and_no_struggles() -> None:
    row = _row("explore", questions=[{"question": "Q", "answer": "A"}], improvements="x")
    topic = build_day(DAY, [row]).groups[0].topics[0]
    assert topic.struggles == []
    assert [(q.question, q.answer) for q in topic.questions] == [("Q", "A")]


def test_week_days_unread() -> None:
    start = date(2026, 11, 2)
    rows = [
        _row(minutes=0, day=date(2026, 11, 2)),
        _row(minutes=0, day=date(2026, 11, 3)),
        _row(minutes=0, day=date(2026, 11, 4)),
        _row(minutes=0, day=date(2026, 11, 6)),
    ]
    viewed = {
        date(2026, 11, 3): T0 + timedelta(hours=1),
        date(2026, 11, 4): T0 - timedelta(hours=1),
    }
    result = build_week_days(start, rows, viewed, today=date(2026, 11, 5))
    by_day = {s.day: s for s in result}
    assert len(result) == 7
    assert (by_day[date(2026, 11, 2)].has_learning, by_day[date(2026, 11, 2)].unread) == (True, True)
    assert (by_day[date(2026, 11, 3)].has_learning, by_day[date(2026, 11, 3)].unread) == (True, False)
    assert by_day[date(2026, 11, 4)].unread is True
    assert (by_day[date(2026, 11, 5)].has_learning, by_day[date(2026, 11, 5)].unread) == (False, False)
    assert (by_day[date(2026, 11, 6)].has_learning, by_day[date(2026, 11, 6)].unread) == (False, False)


def test_content_hash_changes_when_topic_added() -> None:
    first = _row()
    before = build_day(DAY, [first])
    after = build_day(DAY, [first, _row(minutes=5)])
    assert content_hash([before], "今日") == content_hash([build_day(DAY, [first])], "今日")
    assert content_hash([before], "今日") != content_hash([after], "今日")


def test_content_hash_changes_with_label() -> None:
    day = build_day(DAY, [_row()])
    assert content_hash([day], "今日") != content_hash([day], "11月2日に")


def test_build_week_details_returns_each_learned_day_in_order() -> None:
    later = date(2026, 11, 4)
    rows = [_row(day=later, topic="B"), _row(topic="A", summary="Aの要約")]
    days = build_week_details(rows)
    assert [d.day for d in days] == [DAY, later]
    assert days[0].groups[0].topics[0].summary == "Aの要約"


def test_week_start_of_is_monday() -> None:
    assert week_start_of(date(2026, 11, 1)) == date(2026, 10, 26)
    assert week_start_of(date(2026, 11, 2)) == date(2026, 11, 2)


def test_build_week_flattens_struggles_and_questions() -> None:
    rows = [
        _row(improvement_items=[{"text": "s"}], topic="L"),
        _row("explore", minutes=5, topic="E", questions=[{"question": "Q", "answer": "A"}]),
    ]
    week = build_week(DAY, rows)
    assert [(s.topic, s.kind, s.text, s.answer) for s in week.struggles] == [
        ("L", "struggle", "s", None),
        ("E", "question", "Q", "A"),
    ]
    assert [t.topic for t in week.days[0].topics] == ["L", "E"]
