import json
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class ImprovementItem(BaseModel):
    text: str
    aspect_id: str | None = None


class FeedbackResponse(BaseModel):
    id: UUID
    note_id: UUID
    dialogue_session_id: UUID | None
    understanding_level: str
    strength: str
    improvements: str
    improvement_items: list[ImprovementItem] | None = None
    session_type: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("improvement_items", mode="before")
    @classmethod
    def _parse_improvement_items(cls, value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return value


class FeedbackListResponse(BaseModel):
    feedbacks: list[FeedbackResponse]
