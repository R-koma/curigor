from typing import Annotated, Literal

from pydantic import BaseModel, Field

IntakeKey = Literal["topic", "purpose", "source", "prior_knowledge"]

MAX_ANSWER_LENGTH = 200
MAX_SOURCES = 8
MAX_TOPIC_ANSWER_LENGTH = 60


class IntakeOption(BaseModel):
    label: str
    description: str = ""


class IntakeQuestion(BaseModel):
    key: IntakeKey
    header: str
    question: str
    options: list[IntakeOption]
    multi_select: bool = False
    preselected: list[str] = []


class IntakeCard(BaseModel):
    questions: list[IntakeQuestion]


class IntakeAnswers(BaseModel):
    topic: str = Field("", max_length=MAX_TOPIC_ANSWER_LENGTH)
    purpose: str = Field("", max_length=MAX_ANSWER_LENGTH)
    source: list[Annotated[str, Field(max_length=MAX_ANSWER_LENGTH)]] = Field(
        default_factory=list, max_length=MAX_SOURCES
    )
    prior_knowledge: str = Field("", max_length=MAX_ANSWER_LENGTH)
