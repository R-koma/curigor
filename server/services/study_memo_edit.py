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


def apply_study_memo_edit(memo: dict[str, Any], update: StudyMemoUpdate) -> dict[str, Any]:
    changes: dict[str, Any] = update.model_dump(include={"topic", "summary"}, exclude_none=True)
    question_positions = term_positions = None
    if update.questions is not None:
        question_positions = _positions(update.questions, len(memo["questions"]))
        changes["questions"] = [{"question": q.question, "answer": q.answer} for q in update.questions]
    if update.glossary is not None:
        term_positions = _positions(update.glossary, len(memo["glossary"]))
        changes["glossary"] = [{"term": t.term, "reading": t.reading, "meaning": t.meaning} for t in update.glossary]
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
