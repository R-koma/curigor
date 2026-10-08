import base64
import binascii
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from core import config
from core.image_signature import detect_image_mime
from schemas.intake_card import MAX_TOPIC_ANSWER_LENGTH, IntakeAnswers, IntakeCard
from schemas.topic_correction import TopicCorrectionCard

SessionType = Literal["learning", "review", "synthesis"]


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


SttMethod = Literal["segmented", "streaming"]


class VoiceInputFields(BaseModel):
    raw_transcript: str | None = Field(default=None, min_length=1)
    auto_sent: bool = False
    stt_method: SttMethod | None = None
    stt_latency_ms: int | None = Field(default=None, ge=0, le=600_000)

    @model_validator(mode="after")
    def _validate_voice_fields(self) -> Self:
        if self.auto_sent and not self.raw_transcript:
            raise ValueError("auto_sent requires raw_transcript")
        if (self.stt_method is not None or self.stt_latency_ms is not None) and not self.auto_sent:
            raise ValueError("stt fields require auto_sent")
        return self


class StartLearningMessage(VoiceInputFields):
    type: Literal["start_learning"]
    topic: str = Field(..., max_length=MAX_TOPIC_LENGTH)
    learning_goal: str | None = None
    focus_aspects: list[str] | None = None


class StartReviewMessage(BaseModel):
    type: Literal["start_review"]
    note_id: UUID
    focus_aspect_ids: list[str] | None = Field(None, max_length=20)


class StartSynthesisMessage(BaseModel):
    type: Literal["start_synthesis"]
    collection_id: UUID


class ResumeSessionMessage(BaseModel):
    type: Literal["resume_session"]
    session_id: UUID


TopicEdit = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TOPIC_ANSWER_LENGTH)]


class UserMessage(VoiceInputFields):
    type: Literal["user_message"]
    content: str
    client_message_id: UUID
    images: list[ImageAttachment] | None = None
    intake_answers: IntakeAnswers | None = None
    topic_correction_answer: Literal["accept", "decline"] | None = None
    topic_edit: TopicEdit | None = None

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
    | StartSynthesisMessage
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


ProgressStage = Literal["mentioned", "defined", "reasoned", "applied"]


class ProgressAspect(BaseModel):
    name: str
    is_core: bool
    reached_stage: ProgressStage | None


class IntakeSummary(BaseModel):
    purpose: str
    source: str
    prior_knowledge: str


class LearningProgress(BaseModel):
    reached_aspects: list[str]
    target_count: int
    is_complete: bool
    aspects: list[ProgressAspect] = []
    intake: IntakeSummary | None = None


class EndConfirmation(BaseModel):
    creates_note: bool


class AssistantMessageEnd(BaseModel):
    type: Literal["assistant_message_end"] = "assistant_message_end"
    progress: LearningProgress | None = None
    topic: str | None = None
    end_confirmation: EndConfirmation | None = None


class IntakeQuestionMessage(BaseModel):
    type: Literal["intake_question"] = "intake_question"
    content: str
    card: IntakeCard
    topic: str


class TopicCorrectionQuestionMessage(BaseModel):
    type: Literal["topic_correction_question"] = "topic_correction_question"
    content: str
    card: TopicCorrectionCard


class SessionEndedMessage(BaseModel):
    type: Literal["session_ended"] = "session_ended"
    session_id: UUID | None = None
    note_skipped: bool = False


class SessionStartedMessage(BaseModel):
    type: Literal["session_started"] = "session_started"
    session_id: UUID
    session_type: SessionType


class SessionResumedMessage(BaseModel):
    type: Literal["session_resumed"] = "session_resumed"
    session_id: UUID
    session_type: Literal["learning", "review"]
    progress: LearningProgress | None = None
    end_confirmation: EndConfirmation | None = None


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


class TopicEditRejected(BaseModel):
    type: Literal["topic_edit_rejected"] = "topic_edit_rejected"
    detail: str


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    detail: str
