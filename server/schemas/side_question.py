from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from schemas.websocket_message import MAX_MESSAGE_CONTENT_LENGTH

MAX_SIDE_QUOTE_LENGTH = 300
MAX_SIDE_DEPTH = 3


class SideQuestionCreate(BaseModel):
    anchor_message_id: UUID | None = None
    anchor_side_message_id: UUID | None = None
    quote: str = Field(min_length=1, max_length=MAX_SIDE_QUOTE_LENGTH)
    occurrence: int = Field(ge=0)
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CONTENT_LENGTH)

    @model_validator(mode="after")
    def _exactly_one_anchor(self) -> Self:
        if (self.anchor_message_id is None) == (self.anchor_side_message_id is None):
            raise ValueError("Specify exactly one of anchor_message_id and anchor_side_message_id")
        return self


class SideQuestionFollowUp(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CONTENT_LENGTH)


class SideMessageResponse(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str


class SideQuestionResponse(BaseModel):
    id: UUID
    parent_id: UUID | None
    anchor_message_id: UUID | None
    anchor_side_message_id: UUID | None
    quote: str
    occurrence: int
    depth: int
    messages: list[SideMessageResponse]


class SideQuestionsResponse(BaseModel):
    side_questions: list[SideQuestionResponse]


class SideStreamStarted(BaseModel):
    type: Literal["started"] = "started"
    side_question_id: UUID
    user_message_id: UUID
    answer_message_id: UUID


class SideStreamChunk(BaseModel):
    type: Literal["chunk"] = "chunk"
    content: str


class SideStreamEnd(BaseModel):
    type: Literal["end"] = "end"


class SideStreamError(BaseModel):
    type: Literal["error"] = "error"
    code: Literal["side_question_failed", "side_question_anchor_gone"]
    detail: str
