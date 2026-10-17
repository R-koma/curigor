from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class StudyMemoAspect(BaseModel):
    aspect_id: str
    name: str
    summary: str
    is_core: bool


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
