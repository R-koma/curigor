from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class StudyMemoAspect(BaseModel):
    aspect_id: str
    name: str
    summary: str
    is_core: bool
    explained: bool


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


class StudyMemoSummary(BaseModel):
    id: UUID
    topic: str
    source: str
    created_at: datetime
    handed_over: bool


class StudyMemoListResponse(BaseModel):
    memos: list[StudyMemoSummary]
