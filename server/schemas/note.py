import json
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from graph.aspect_map import parse_aspect_map, with_aspect_ids
from schemas.intake_card import MAX_TOPIC_ANSWER_LENGTH
from schemas.websocket_message import IntakeSummary

MAX_NOTE_SUMMARY_LENGTH = 1000
MAX_NOTE_CONTENT_LENGTH = 20000
MAX_NOTE_CATEGORY_LENGTH = 100

NoteStatus = Literal["active", "archived"]
NoteTopic = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TOPIC_ANSWER_LENGTH)]
NoteCategoryName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_NOTE_CATEGORY_LENGTH)
]


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

    @field_validator("aspect_map", mode="before")
    @classmethod
    def _parse_aspect_map(cls, value: Any) -> Any:
        aspect_map = parse_aspect_map(value)
        return with_aspect_ids(aspect_map) if aspect_map is not None else None

    @field_validator("intake", mode="before")
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
    topic: NoteTopic | None = None
    content: Annotated[str, StringConstraints(min_length=1, max_length=MAX_NOTE_CONTENT_LENGTH)] | None = None
    summary: Annotated[str, StringConstraints(max_length=MAX_NOTE_SUMMARY_LENGTH)] | None = None
    status: NoteStatus | None = None
    category: NoteCategoryName | None = None


class NoteListResponse(BaseModel):
    notes: list[NoteResponse]
