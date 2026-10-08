from __future__ import annotations

from collections import Counter

from evals.feedback import LEVELS, load_records
from evals.taxonomy import ROUTES, SOURCES
from evals.tools.capture import CAPTURED_BY

_SESSION_TYPES = frozenset({"learning", "review"})


def test_ids_are_unique() -> None:
    counts = Counter(record["id"] for record in load_records())
    assert [record_id for record_id, count in counts.items() if count > 1] == []


def test_value_spaces_are_registered() -> None:
    problems = [
        f"{record['id']}: {field}={value!r}"
        for record in load_records()
        for field, value, allowed in (
            ("source", record["source"], SOURCES),
            ("session_type", record["session_type"], _SESSION_TYPES),
            ("output.understanding_level", record["output"]["understanding_level"], LEVELS),
            ("human_level", record["human_level"], (*LEVELS, None)),
            ("meta.route", record["meta"].get("route"), (*ROUTES, "legacy", None)),
        )
        if value not in allowed
    ]
    assert not problems, "\n".join(problems)


def test_labeled_records_carry_a_timestamp() -> None:
    problems = [
        record["id"]
        for record in load_records()
        if (record["human_level"] is None) != (record["annotated_at"] is None)
    ]
    assert problems == []


def test_captured_records_carry_the_assessment_input() -> None:
    problems = [
        record["id"]
        for record in load_records()
        if record["meta"].get("captured_by") == CAPTURED_BY
        and not {"topic", "conversation", "note_text", "aspect_map"} <= set(record["input"])
    ]
    assert problems == []
