from uuid import UUID

from pydantic import BaseModel


class TranscriptionResponse(BaseModel):
    text: str


class TranscriptFormatRequest(BaseModel):
    text: str
    dialogue_session_id: UUID


class TranscriptFormatResponse(BaseModel):
    text: str
