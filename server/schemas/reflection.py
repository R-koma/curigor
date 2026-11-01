from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from schemas.speech import SpeechSpeed
from schemas.study_memo import StudyMemoQuestion

ReflectionSessionType = Literal["learning", "explore", "review"]


class ReflectionTopic(BaseModel):
    session_type: ReflectionSessionType
    source_id: UUID
    topic: str
    summary: str
    struggles: list[str]
    questions: list[StudyMemoQuestion]


class ReflectionGroup(BaseModel):
    session_type: ReflectionSessionType
    topics: list[ReflectionTopic]


class DayReflection(BaseModel):
    day: date
    groups: list[ReflectionGroup]


class WeekDayStatus(BaseModel):
    day: date
    has_learning: bool
    unread: bool


class WeekDaysResponse(BaseModel):
    days: list[WeekDayStatus]


class WeekTopic(BaseModel):
    session_type: ReflectionSessionType
    topic: str


class WeekReflectionDay(BaseModel):
    day: date
    topics: list[WeekTopic]


class WeekStruggle(BaseModel):
    topic: str
    kind: Literal["struggle", "question"]
    text: str
    answer: str | None = None


class WeekReflection(BaseModel):
    week_start: date
    days: list[WeekReflectionDay]
    struggles: list[WeekStruggle]


class ReflectionScriptResponse(BaseModel):
    sentences: list[str]


class ReflectionSpeechRequest(BaseModel):
    text: str
    speed: SpeechSpeed = 1.0
