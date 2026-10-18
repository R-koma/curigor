from typing import Any

import pytest
from pydantic import ValidationError

from schemas.study_memo import StudyMemoUpdate
from services.study_memo_edit import StudyMemoEditError, apply_study_memo_edit


def _memo() -> dict[str, Any]:
    return {
        "topic": "二分探索",
        "summary": "",
        "overview": [
            {
                "aspect_id": "a",
                "name": "比較",
                "summary": "",
                "is_core": True,
                "question_indices": [0, 2],
                "term_indices": [1],
            },
            {
                "aspect_id": "b",
                "name": "計算量",
                "summary": "",
                "is_core": False,
                "question_indices": [1],
                "term_indices": [0],
            },
        ],
        "questions": [
            {"question": "q0", "answer": "a0"},
            {"question": "q1", "answer": "a1"},
            {"question": "q2", "answer": "a2"},
        ],
        "glossary": [
            {"term": "t0", "reading": "", "meaning": "m0"},
            {"term": "t1", "reading": "", "meaning": "m1"},
        ],
    }


def test_topic_and_summary_only_leave_the_lists_untouched() -> None:
    changes = apply_study_memo_edit(_memo(), StudyMemoUpdate(topic=" 二分探索の基本 ", summary="要約"))

    assert changes == {"topic": "二分探索の基本", "summary": "要約"}


def test_deleting_a_question_moves_the_remaining_indices_in_the_overview() -> None:
    update = StudyMemoUpdate.model_validate(
        {"questions": [{"index": 0, "question": "q0", "answer": "a0"}, {"index": 2, "question": "q2!", "answer": ""}]}
    )

    changes = apply_study_memo_edit(_memo(), update)

    assert changes["questions"] == [{"question": "q0", "answer": "a0"}, {"question": "q2!", "answer": ""}]
    assert [a["question_indices"] for a in changes["overview"]] == [[0, 1], []]
    assert [a["term_indices"] for a in changes["overview"]] == [[1], [0]]


def test_deleting_a_term_moves_the_remaining_indices_in_the_overview() -> None:
    update = StudyMemoUpdate.model_validate({"glossary": [{"index": 1, "term": "t1", "reading": "", "meaning": "m1"}]})

    changes = apply_study_memo_edit(_memo(), update)

    assert changes["glossary"] == [{"term": "t1", "reading": "", "meaning": "m1"}]
    assert [a["term_indices"] for a in changes["overview"]] == [[0], []]


def test_an_index_past_the_end_is_rejected() -> None:
    update = StudyMemoUpdate.model_validate({"questions": [{"index": 3, "question": "q", "answer": ""}]})

    with pytest.raises(StudyMemoEditError):
        apply_study_memo_edit(_memo(), update)


def test_duplicate_indices_are_rejected() -> None:
    with pytest.raises(ValidationError):
        StudyMemoUpdate.model_validate(
            {"questions": [{"index": 0, "question": "q", "answer": ""}, {"index": 0, "question": "q", "answer": ""}]}
        )


def test_an_empty_topic_is_rejected() -> None:
    with pytest.raises(ValidationError):
        StudyMemoUpdate(topic="  ")
