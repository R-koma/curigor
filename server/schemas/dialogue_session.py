from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from schemas.intake_card import IntakeAnswers, IntakeCard


class FeedbackData(BaseModel):
    understanding_level: str
    strength: str
    improvements: str


class NoteStatusResponse(BaseModel):
    status: str
    session_type: str
    note_id: UUID | None = None
    topic: str | None = None
    summary: str | None = None
    feedback: FeedbackData | None = None


class ActiveSessionResponse(BaseModel):
    session_id: UUID
    session_type: Literal["learning", "review"]
    status: Literal["in_progress", "disconnect"]
    started_at: datetime
    topic: str | None = None
    note_id: UUID | None = None


class DialogueImageData(BaseModel):
    id: UUID
    mime_type: str
    image_order: int


class DialogueMessageData(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    message_order: int
    images: list[DialogueImageData] = []
    intake_card: IntakeCard | None = None
    intake_answers: IntakeAnswers | None = None


class SessionMessagesResponse(BaseModel):
    session_id: UUID
    session_type: Literal["learning", "review"]
    status: str
    note_id: UUID | None = None
    topic: str | None = None
    messages: list[DialogueMessageData]
