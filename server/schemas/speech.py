from uuid import UUID

from pydantic import BaseModel


class SpeechRequest(BaseModel):
    text: str
    dialogue_session_id: UUID
