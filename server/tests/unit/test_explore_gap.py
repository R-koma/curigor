import json
from typing import Any
from uuid import uuid4

from schemas.websocket_message import ExploreSource
from services.explore_gap import gap_opening_utterance, gap_question, resolve_gap

NOTE_ID = uuid4()
OLDER = {"id": uuid4(), "improvements": "古い", "improvement_items": None}
LATEST = {
    "id": uuid4(),
    "improvements": "境界の扱いが曖昧\nその他",
    "improvement_items": json.dumps(
        [{"text": "境界の扱いが曖昧", "aspect_id": "a1"}, {"text": "その他", "aspect_id": None}]
    ),
}
NOTE: dict[str, Any] = {
    "content": "本文",
    "aspect_map": json.dumps(
        {"root": "t", "aspects": [{"name": "境界条件", "summary": "", "coverage": "partial", "children": []}]}
    ),
}


def _source(feedback_id: Any, index: int = 0) -> ExploreSource:
    return ExploreSource(note_id=NOTE_ID, feedback_id=feedback_id, improvement_index=index)


def test_resolve_gap_reads_the_item_and_aspect_name() -> None:
    gap = resolve_gap(NOTE, [OLDER, LATEST], _source(LATEST["id"]))

    assert gap == {
        "note_id": str(NOTE_ID),
        "feedback_id": str(LATEST["id"]),
        "improvement_index": 0,
        "improvement": "境界の扱いが曖昧",
        "note_content": "本文",
        "aspect_id": "a1",
        "aspect_name": "境界条件",
    }


def test_resolve_gap_omits_aspect_for_an_unlinked_item() -> None:
    gap = resolve_gap(NOTE, [LATEST], _source(LATEST["id"], 1))

    assert gap is not None
    assert gap["improvement"] == "その他"
    assert "aspect_id" not in gap
    assert "aspect_name" not in gap


def test_resolve_gap_omits_aspect_not_in_the_map() -> None:
    feedback = {**LATEST, "improvement_items": json.dumps([{"text": "x", "aspect_id": "a9"}])}

    gap = resolve_gap(NOTE, [feedback], _source(feedback["id"]))

    assert gap is not None
    assert "aspect_id" not in gap


def test_resolve_gap_splits_legacy_improvements_like_the_client() -> None:
    legacy = {"id": uuid4(), "improvements": "・一つ目\n\n- 二つ目", "improvement_items": None}

    gap = resolve_gap(NOTE, [legacy], _source(legacy["id"], 1))

    assert gap is not None
    assert gap["improvement"] == "二つ目"
    assert "aspect_id" not in gap


def test_resolve_gap_rejects_a_feedback_that_is_not_the_latest() -> None:
    assert resolve_gap(NOTE, [OLDER, LATEST], _source(OLDER["id"])) is None


def test_resolve_gap_rejects_an_index_out_of_range() -> None:
    assert resolve_gap(NOTE, [LATEST], _source(LATEST["id"], 2)) is None


def test_resolve_gap_rejects_no_feedbacks() -> None:
    assert resolve_gap(NOTE, [], _source(uuid4())) is None


def test_gap_opening_utterance() -> None:
    gap = resolve_gap(NOTE, [LATEST], _source(LATEST["id"]))

    assert gap is not None
    assert gap_opening_utterance(gap) == "改善点「境界の扱いが曖昧」を理解したい"


def test_gap_question_turns_the_improvement_into_a_question() -> None:
    gap = resolve_gap(NOTE, [LATEST], _source(LATEST["id"]))

    assert gap is not None
    assert gap_question(gap) == "「境界の扱いが曖昧」と指摘された部分は、どういうことか"


def test_gap_question_drops_the_trailing_period() -> None:
    feedback = {**LATEST, "improvement_items": json.dumps([{"text": "具体例が無い。", "aspect_id": None}])}
    gap = resolve_gap(NOTE, [feedback], _source(feedback["id"]))

    assert gap is not None
    assert gap_question(gap) == "「具体例が無い」と指摘された部分は、どういうことか"


def test_resolve_gap_rejects_an_item_without_text() -> None:
    for item in ({"aspect_id": "a1"}, {"text": None}, {"text": 3}, "text"):
        feedback = {**LATEST, "improvement_items": json.dumps([item])}
        assert resolve_gap(NOTE, [feedback], _source(feedback["id"])) is None
