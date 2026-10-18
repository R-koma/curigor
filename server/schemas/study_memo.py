from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, model_validator

from schemas.intake_card import MAX_TOPIC_ANSWER_LENGTH

MAX_MEMO_SUMMARY_LENGTH = 1000
MAX_MEMO_QUESTION_LENGTH = 500
MAX_MEMO_ANSWER_LENGTH = 2000
MAX_MEMO_TERM_LENGTH = 60
MAX_MEMO_READING_LENGTH = 60
MAX_MEMO_MEANING_LENGTH = 500


class StudyMemoAspect(BaseModel):
    aspect_id: str
    name: str
    summary: str
    is_core: bool
    question_indices: list[int] = []
    term_indices: list[int] = []


class StudyMemoTerm(BaseModel):
    term: str
    reading: str
    meaning: str


class StudyMemoQuestion(BaseModel):
    question: str
    answer: str


class StudyMemoResponse(BaseModel):
    id: UUID
    topic: str
    source: str
    summary: str
    overview: list[StudyMemoAspect]
    glossary: list[StudyMemoTerm]
    questions: list[StudyMemoQuestion]
    created_at: datetime


class StudyMemoAspectName(BaseModel):
    name: str
    is_core: bool


class StudyMemoSummary(BaseModel):
    id: UUID
    topic: str
    source: str
    created_at: datetime
    handed_over: bool
    aspects: list[StudyMemoAspectName]
    glossary_count: int
    question_count: int


class StudyMemoListResponse(BaseModel):
    memos: list[StudyMemoSummary]


def _text(max_length: int, *, required: bool = False) -> StringConstraints:
    return StringConstraints(strip_whitespace=True, min_length=1 if required else 0, max_length=max_length)


class StudyMemoQuestionEdit(BaseModel):
    index: Annotated[int, Field(ge=0)]
    question: Annotated[str, _text(MAX_MEMO_QUESTION_LENGTH, required=True)]
    answer: Annotated[str, _text(MAX_MEMO_ANSWER_LENGTH)]


class StudyMemoTermEdit(BaseModel):
    index: Annotated[int, Field(ge=0)]
    term: Annotated[str, _text(MAX_MEMO_TERM_LENGTH, required=True)]
    reading: Annotated[str, _text(MAX_MEMO_READING_LENGTH)]
    meaning: Annotated[str, _text(MAX_MEMO_MEANING_LENGTH)]


def _unique_indices(items: list[StudyMemoQuestionEdit] | list[StudyMemoTermEdit] | None) -> None:
    if items is not None and len({item.index for item in items}) != len(items):
        raise ValueError("indices must be unique")


class StudyMemoUpdate(BaseModel):
    topic: Annotated[str, _text(MAX_TOPIC_ANSWER_LENGTH, required=True)] | None = None
    summary: Annotated[str, _text(MAX_MEMO_SUMMARY_LENGTH)] | None = None
    questions: list[StudyMemoQuestionEdit] | None = None
    glossary: list[StudyMemoTermEdit] | None = None

    @model_validator(mode="after")
    def _check_indices(self) -> Self:
        _unique_indices(self.questions)
        _unique_indices(self.glossary)
        return self
