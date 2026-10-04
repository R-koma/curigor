import json
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from schemas.websocket_message import IntakeSummary


class NoteResponse(BaseModel):
    id: UUID
    user_id: str
    topic: str
    content: str
    summary: str | None
    status: str
    category: str | None = None
    aspect_map: dict[str, Any] | None = None
    intake: IntakeSummary | None = None
    collection_id: UUID | None = None
    suggested_collection: str | None = None
    manually_edited_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    review_count: int = 0

    model_config = ConfigDict(from_attributes=True)

    @field_validator("aspect_map", "intake", mode="before")
    @classmethod
    def _parse_json_column(cls, value: Any) -> Any:
        if value is None or isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return value


class NoteUpdate(BaseModel):
    topic: str | None = None
    content: str | None = None
    summary: str | None = None
    status: str | None = None
    category: str | None = None


class NoteListResponse(BaseModel):
    notes: list[NoteResponse]
