from collections.abc import Sequence
from typing import Any

from schemas.study_memo import StudyMemoQuestionEdit, StudyMemoTermEdit, StudyMemoUpdate


class StudyMemoEditError(ValueError):
    pass


def _positions(items: Sequence[StudyMemoQuestionEdit | StudyMemoTermEdit], count: int) -> dict[int, int]:
    if any(item.index >= count for item in items):
        raise StudyMemoEditError("index out of range")
    return {item.index: position for position, item in enumerate(items)}


def _remap(indices: list[int], positions: dict[int, int] | None) -> list[int]:
    if positions is None:
        return indices
    return [positions[i] for i in indices if i in positions]


_QUESTION_EXTRAS = ("quote", "from_side")
_TERM_EXTRAS = ("from_side",)


def _extras(original: dict[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    return {key: original[key] for key in keys if key in original}


def _edited_questions(
    memo: dict[str, Any], items: Sequence[StudyMemoQuestionEdit], positions: dict[int, int]
) -> list[dict[str, Any]]:
    edited: list[dict[str, Any]] = []
    for item in items:
        original = memo["questions"][item.index]
        question: dict[str, Any] = {"question": item.question, "answer": item.answer}
        question.update(_extras(original, _QUESTION_EXTRAS))
        if "parent_index" in original:
            parent = original["parent_index"]
            question["parent_index"] = positions.get(parent) if parent is not None else None
        edited.append(question)
    return edited


def apply_study_memo_edit(memo: dict[str, Any], update: StudyMemoUpdate) -> dict[str, Any]:
    changes: dict[str, Any] = update.model_dump(include={"topic", "summary"}, exclude_none=True)
    question_positions = term_positions = None
    if update.questions is not None:
        question_positions = _positions(update.questions, len(memo["questions"]))
        changes["questions"] = _edited_questions(memo, update.questions, question_positions)
    if update.glossary is not None:
        term_positions = _positions(update.glossary, len(memo["glossary"]))
        changes["glossary"] = [
            {
                "term": t.term,
                "reading": t.reading,
                "meaning": t.meaning,
                **_extras(memo["glossary"][t.index], _TERM_EXTRAS),
            }
            for t in update.glossary
        ]
    if question_positions is not None or term_positions is not None:
        changes["overview"] = [
            {
                **aspect,
                "question_indices": _remap(aspect.get("question_indices", []), question_positions),
                "term_indices": _remap(aspect.get("term_indices", []), term_positions),
            }
            for aspect in memo["overview"]
        ]
    return changes
