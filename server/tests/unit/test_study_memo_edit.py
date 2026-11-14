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


def _side_memo() -> dict[str, Any]:
    memo = _memo()
    memo["questions"] = [
        {"question": "q0", "answer": "a0"},
        {"question": "q1", "answer": "a1", "quote": "中央", "parent_index": None, "from_side": True},
        {"question": "q2", "answer": "a2", "quote": "比較", "parent_index": 1, "from_side": True},
    ]
    memo["glossary"] = [
        {"term": "t0", "reading": "", "meaning": "m0"},
        {"term": "t1", "reading": "", "meaning": "m1", "from_side": True},
    ]
    return memo


def _questions(*items: tuple[int, str]) -> list[dict[str, Any]]:
    return [{"index": i, "question": q, "answer": ""} for i, q in items]


def test_edit_preserves_quote_parent_and_from_side() -> None:
    update = StudyMemoUpdate.model_validate(
        {
            "questions": _questions((0, "q0"), (1, "q1!"), (2, "q2")),
            "glossary": [
                {"index": 0, "term": "t0", "reading": "", "meaning": "m0"},
                {"index": 1, "term": "t1!", "reading": "", "meaning": "m1"},
            ],
        }
    )

    changes = apply_study_memo_edit(_side_memo(), update)

    assert changes["questions"][0] == {"question": "q0", "answer": ""}
    assert changes["questions"][1] == {
        "question": "q1!",
        "answer": "",
        "quote": "中央",
        "parent_index": None,
        "from_side": True,
    }
    assert changes["questions"][2]["parent_index"] == 1
    assert changes["glossary"][0] == {"term": "t0", "reading": "", "meaning": "m0"}
    assert changes["glossary"][1] == {"term": "t1!", "reading": "", "meaning": "m1", "from_side": True}


def test_edit_remaps_parent_index_after_deleting_earlier_question() -> None:
    update = StudyMemoUpdate.model_validate({"questions": _questions((1, "q1"), (2, "q2"))})

    changes = apply_study_memo_edit(_side_memo(), update)

    assert changes["questions"][1]["parent_index"] == 0
    assert changes["questions"][1]["quote"] == "比較"


def test_edit_deleting_parent_clears_parent_index_of_child() -> None:
    update = StudyMemoUpdate.model_validate({"questions": _questions((0, "q0"), (2, "q2"))})

    changes = apply_study_memo_edit(_side_memo(), update)

    assert changes["questions"][1] == {
        "question": "q2",
        "answer": "",
        "quote": "比較",
        "parent_index": None,
        "from_side": True,
    }
    assert [a["question_indices"] for a in changes["overview"]] == [[0, 1], []]


def test_old_memo_without_new_fields_validates_and_edits() -> None:
    from schemas.study_memo import StudyMemoQuestion, StudyMemoTerm

    question = StudyMemoQuestion.model_validate({"question": "q", "answer": "a"})
    term = StudyMemoTerm.model_validate({"term": "t", "reading": "", "meaning": "m"})
    assert (question.quote, question.parent_index, question.from_side) == (None, None, False)
    assert term.from_side is False

    changes = apply_study_memo_edit(_memo(), StudyMemoUpdate.model_validate({"questions": _questions((2, "q2"))}))

    assert changes["questions"] == [{"question": "q2", "answer": ""}]
