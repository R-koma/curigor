import base64
import binascii
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from core import config
from core.image_signature import detect_image_mime
from schemas.intake_card import IntakeAnswers, IntakeCard


class ImageAttachment(BaseModel):
    mime_type: Literal["image/jpeg", "image/png", "image/webp"]
    data: str  # base64（data URL プレフィックスは含めない）

    @field_validator("data")
    @classmethod
    def _validate_decoded_size(cls, value: str) -> str:
        try:
            decoded = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("data must be valid base64") from exc
        if len(decoded) == 0:
            raise ValueError("image is empty")
        if len(decoded) > config.MAX_IMAGE_BYTES:
            raise ValueError(f"image exceeds {config.MAX_IMAGE_BYTES} bytes")
        return value

    @model_validator(mode="after")
    def _validate_content_matches_mime(self) -> "ImageAttachment":
        decoded = base64.b64decode(self.data, validate=True)
        if detect_image_mime(decoded) != self.mime_type:
            raise ValueError("image content does not match declared mime_type")
        return self


MAX_TOPIC_LENGTH = 2000


class StartLearningMessage(BaseModel):
    type: Literal["start_learning"]
    topic: str = Field(..., max_length=MAX_TOPIC_LENGTH)
    learning_goal: str | None = None
    focus_aspects: list[str] | None = None


class StartReviewMessage(BaseModel):
    type: Literal["start_review"]
    note_id: UUID


class ResumeSessionMessage(BaseModel):
    type: Literal["resume_session"]
    session_id: UUID


class UserMessage(BaseModel):
    type: Literal["user_message"]
    content: str
    client_message_id: UUID
    images: list[ImageAttachment] | None = None
    intake_answers: IntakeAnswers | None = None
    raw_transcript: str | None = Field(default=None, min_length=1)

    @field_validator("images")
    @classmethod
    def _validate_image_count(cls, value: list[ImageAttachment] | None) -> list[ImageAttachment] | None:
        if value and len(value) > config.MAX_IMAGES_PER_MESSAGE:
            raise ValueError(f"at most {config.MAX_IMAGES_PER_MESSAGE} images per message")
        return value


class CancelLastMessageRequest(BaseModel):
    type: Literal["cancel_last_message"]


class EndSessionMessage(BaseModel):
    type: Literal["end_session"]


IncomingMessage = Annotated[
    StartLearningMessage
    | StartReviewMessage
    | ResumeSessionMessage
    | UserMessage
    | CancelLastMessageRequest
    | EndSessionMessage,
    Field(discriminator="type"),
]


class AssistantMessage(BaseModel):
    type: Literal["assistant_message"] = "assistant_message"
    content: str


class AssistantMessageChunk(BaseModel):
    type: Literal["assistant_message_chunk"] = "assistant_message_chunk"
    content: str


class LearningProgress(BaseModel):
    reached_aspects: list[str]
    target_count: int
    is_complete: bool


class AssistantMessageEnd(BaseModel):
    type: Literal["assistant_message_end"] = "assistant_message_end"
    progress: LearningProgress | None = None


class IntakeQuestionMessage(BaseModel):
    type: Literal["intake_question"] = "intake_question"
    content: str
    card: IntakeCard
    topic: str


class NoteGeneratedMessage(BaseModel):
    type: Literal["note_generated"] = "note_generated"
    note_id: UUID
    topic: str
    summary: str


class FeedbackGeneratedMessage(BaseModel):
    type: Literal["feedback_generated"] = "feedback_generated"
    understanding_level: str
    strength: str
    improvements: str


class SessionEndedMessage(BaseModel):
    type: Literal["session_ended"] = "session_ended"
    session_id: UUID | None = None


class SessionStartedMessage(BaseModel):
    type: Literal["session_started"] = "session_started"
    session_id: UUID
    session_type: Literal["learning", "review"]


class SessionResumedMessage(BaseModel):
    type: Literal["session_resumed"] = "session_resumed"
    session_id: UUID
    session_type: Literal["learning", "review"]
    progress: LearningProgress | None = None


class CancelLastMessageSuccess(BaseModel):
    type: Literal["cancel_last_message_success"] = "cancel_last_message_success"
    cancelled_content: str


class PendingMessageRolledBack(BaseModel):
    """再開時に、応答が返らないまま残っていたユーザーメッセージを取り消したことを伝える。"""

    type: Literal["pending_message_rolled_back"] = "pending_message_rolled_back"
    content: str


class CancelLastMessageError(BaseModel):
    type: Literal["cancel_last_message_error"] = "cancel_last_message_error"
    detail: str


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    detail: str
