import json
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class ImprovementItem(BaseModel):
    headline: str | None = None
    text: str
    aspect_id: str | None = None


class ReviewResultItem(BaseModel):
    point_id: str
    point: str
    question: str
    status: Literal["explained", "explained_with_hint", "explained_after_note", "not_explained", "not_asked"]
    aspect_id: str | None = None


class FeedbackResponse(BaseModel):
    id: UUID
    note_id: UUID
    dialogue_session_id: UUID | None
    understanding_level: str
    strength: str
    improvements: str
    improvement_items: list[ImprovementItem] | None = None
    review_results: list[ReviewResultItem] | None = None
    session_type: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("improvement_items", "review_results", mode="before")
    @classmethod
    def _parse_json_list(cls, value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return value


class FeedbackListResponse(BaseModel):
    feedbacks: list[FeedbackResponse]
