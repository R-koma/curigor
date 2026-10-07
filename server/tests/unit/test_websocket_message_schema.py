import base64
import json
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from core import config
from schemas.intake_card import IntakeAnswers, IntakeCard
from schemas.websocket_message import (
    AssistantMessageEnd,
    ImageAttachment,
    IncomingMessage,
    IntakeQuestionMessage,
    SessionEndedMessage,
    StartLearningMessage,
    StartReviewMessage,
    StartSynthesisMessage,
    TopicCorrectionQuestionMessage,
    UserMessage,
)

_adapter: TypeAdapter[IncomingMessage] = TypeAdapter(IncomingMessage)

_PNG_BYTES = b"\x89PNG\r\n\x1a\n"
_JPEG_BYTES = b"\xff\xd8\xff\xe0"
_WEBP_BYTES = b"RIFF\x00\x00\x00\x00WEBP"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def test_user_message_without_images_parses() -> None:
    msg = _adapter.validate_python({"type": "user_message", "content": "hi", "client_message_id": str(uuid4())})
    assert isinstance(msg, UserMessage)
    assert msg.images is None


def test_user_message_requires_client_message_id() -> None:
    with pytest.raises(ValidationError):
        _adapter.validate_python({"type": "user_message", "content": "hi"})


def test_user_message_with_image_parses() -> None:
    msg = _adapter.validate_python(
        {
            "type": "user_message",
            "content": "見て",
            "client_message_id": str(uuid4()),
            "images": [{"mime_type": "image/png", "data": _b64(_PNG_BYTES)}],
        }
    )
    assert isinstance(msg, UserMessage)
    assert msg.images is not None
    assert msg.images[0].mime_type == "image/png"


@pytest.mark.parametrize(
    ("mime_type", "data"),
    [
        ("image/png", _PNG_BYTES),
        ("image/jpeg", _JPEG_BYTES),
        ("image/webp", _WEBP_BYTES),
    ],
)
def test_accepts_matching_signature(mime_type: str, data: bytes) -> None:
    attachment = ImageAttachment(mime_type=mime_type, data=_b64(data))  # type: ignore[arg-type]
    assert attachment.mime_type == mime_type


def test_rejects_mime_mismatch() -> None:
    with pytest.raises(ValidationError, match="does not match"):
        ImageAttachment(mime_type="image/png", data=_b64(_JPEG_BYTES))


def test_rejects_non_image_content() -> None:
    with pytest.raises(ValidationError, match="does not match"):
        ImageAttachment(mime_type="image/png", data=_b64(b"not an image"))


def test_rejects_unsupported_mime() -> None:
    with pytest.raises(ValidationError):
        ImageAttachment(mime_type="image/gif", data=_b64(_PNG_BYTES))  # type: ignore[arg-type]


def test_rejects_invalid_base64() -> None:
    with pytest.raises(ValidationError, match="valid base64"):
        ImageAttachment(mime_type="image/png", data="!!!not base64!!!")


def test_rejects_empty_image() -> None:
    with pytest.raises(ValidationError, match="empty"):
        ImageAttachment(mime_type="image/png", data=_b64(b""))


def test_rejects_oversized_image() -> None:
    oversized = _b64(b"a" * (config.MAX_IMAGE_BYTES + 1))
    with pytest.raises(ValidationError, match="exceeds"):
        ImageAttachment(mime_type="image/png", data=oversized)


def test_rejects_too_many_images() -> None:
    images = [{"mime_type": "image/png", "data": _b64(_PNG_BYTES)}] * (config.MAX_IMAGES_PER_MESSAGE + 1)
    with pytest.raises(ValidationError, match="at most"):
        _adapter.validate_python(
            {"type": "user_message", "content": "hi", "client_message_id": str(uuid4()), "images": images}
        )


def test_start_learning_ignores_legacy_target_depth() -> None:
    msg = _adapter.validate_python({"type": "start_learning", "topic": "二分探索", "target_depth": "explain"})
    assert isinstance(msg, StartLearningMessage)
    assert not hasattr(msg, "target_depth")


def test_user_message_accepts_intake_answers() -> None:
    msg = _adapter.validate_python(
        {
            "type": "user_message",
            "content": "目的: 仕事で使う",
            "client_message_id": str(uuid4()),
            "intake_answers": {
                "purpose": "仕事で使う",
                "source": ["公式ドキュメント", "Udemy"],
                "prior_knowledge": "",
            },
        }
    )
    assert isinstance(msg, UserMessage)
    assert msg.intake_answers == IntakeAnswers(purpose="仕事で使う", source=["公式ドキュメント", "Udemy"])


def test_user_message_rejects_oversized_intake_answer() -> None:
    with pytest.raises(ValidationError):
        _adapter.validate_python(
            {
                "type": "user_message",
                "content": "x",
                "client_message_id": str(uuid4()),
                "intake_answers": {"purpose": "あ" * 201},
            }
        )


def test_user_message_rejects_oversized_source_entry() -> None:
    with pytest.raises(ValidationError):
        _adapter.validate_python(
            {
                "type": "user_message",
                "content": "x",
                "client_message_id": str(uuid4()),
                "intake_answers": {"source": ["あ" * 201]},
            }
        )


def test_user_message_rejects_too_many_sources() -> None:
    with pytest.raises(ValidationError):
        _adapter.validate_python(
            {
                "type": "user_message",
                "content": "x",
                "client_message_id": str(uuid4()),
                "intake_answers": {"source": [f"s{i}" for i in range(9)]},
            }
        )


def test_intake_question_message_serializes_card() -> None:
    card = IntakeCard.model_validate(
        {
            "questions": [
                {
                    "key": "source",
                    "header": "教材",
                    "question": "何を使って学びますか？",
                    "options": [{"label": "書籍"}],
                    "multi_select": True,
                }
            ]
        }
    )
    dumped = IntakeQuestionMessage(content="lead", card=card, topic="React Hooks").model_dump()
    assert dumped["type"] == "intake_question"
    assert dumped["card"]["questions"][0]["options"][0] == {"label": "書籍", "description": ""}
    assert dumped["card"]["questions"][0]["preselected"] == []


def test_start_learning_rejects_oversized_topic() -> None:
    with pytest.raises(ValidationError):
        _adapter.validate_python({"type": "start_learning", "topic": "あ" * 2001})


class TestUserMessageRawTranscript:
    def test_defaults_to_none(self) -> None:
        msg = UserMessage(type="user_message", content="こんにちは", client_message_id=uuid4())
        assert msg.raw_transcript is None

    def test_accepts_a_transcript(self) -> None:
        msg = UserMessage(
            type="user_message", content="こんにちは", client_message_id=uuid4(), raw_transcript="こんにちわ"
        )
        assert msg.raw_transcript == "こんにちわ"

    def test_rejects_an_empty_transcript(self) -> None:
        with pytest.raises(ValidationError):
            UserMessage(type="user_message", content="こんにちは", client_message_id=uuid4(), raw_transcript="")


class TestStartLearningRawTranscript:
    def test_defaults_to_none(self) -> None:
        msg = _adapter.validate_python({"type": "start_learning", "topic": "二分探索"})
        assert isinstance(msg, StartLearningMessage)
        assert msg.raw_transcript is None

    def test_accepts_a_transcript(self) -> None:
        msg = _adapter.validate_python(
            {"type": "start_learning", "topic": "二分探索", "raw_transcript": "にぶんたんさく"}
        )
        assert isinstance(msg, StartLearningMessage)
        assert msg.raw_transcript == "にぶんたんさく"

    def test_rejects_an_empty_transcript(self) -> None:
        with pytest.raises(ValidationError):
            _adapter.validate_python({"type": "start_learning", "topic": "二分探索", "raw_transcript": ""})


def _user_message(**extra: object) -> dict[str, object]:
    return {"type": "user_message", "content": "説明します", "client_message_id": str(uuid4()), **extra}


def test_auto_sent_defaults_to_false() -> None:
    msg = UserMessage.model_validate(_user_message())

    assert msg.auto_sent is False


def test_auto_sent_requires_a_raw_transcript() -> None:
    with pytest.raises(ValidationError):
        UserMessage.model_validate(_user_message(auto_sent=True))
    with pytest.raises(ValidationError):
        StartLearningMessage.model_validate({"type": "start_learning", "topic": "二分探索", "auto_sent": True})


def test_auto_sent_is_accepted_with_a_raw_transcript() -> None:
    msg = UserMessage.model_validate(_user_message(raw_transcript="せつめいします", auto_sent=True))
    start = StartLearningMessage.model_validate(
        {"type": "start_learning", "topic": "二分探索", "raw_transcript": "にぶんたんさく", "auto_sent": True}
    )

    assert msg.auto_sent is True
    assert start.auto_sent is True


def test_start_synthesis_message_is_parsed() -> None:
    collection_id = uuid4()
    msg = _adapter.validate_json(json.dumps({"type": "start_synthesis", "collection_id": str(collection_id)}))

    assert isinstance(msg, StartSynthesisMessage)
    assert msg.collection_id == collection_id


def test_user_message_accepts_stt_fields_with_auto_sent() -> None:
    msg = UserMessage(
        type="user_message",
        content="半分に絞ります",
        client_message_id=uuid4(),
        raw_transcript="半分に絞ります",
        auto_sent=True,
        stt_method="segmented",
        stt_latency_ms=820,
    )
    assert (msg.stt_method, msg.stt_latency_ms) == ("segmented", 820)


def test_stt_fields_require_auto_sent() -> None:
    with pytest.raises(ValidationError):
        UserMessage(
            type="user_message",
            content="半分",
            client_message_id=uuid4(),
            raw_transcript="半分",
            stt_method="segmented",
        )


def test_stt_method_rejects_unknown_values() -> None:
    with pytest.raises(ValidationError):
        StartLearningMessage.model_validate(
            {
                "type": "start_learning",
                "topic": "二分探索",
                "raw_transcript": "二分探索",
                "auto_sent": True,
                "stt_method": "whisper",
            }
        )


def test_stt_latency_rejects_negative_values() -> None:
    with pytest.raises(ValidationError):
        StartLearningMessage(
            type="start_learning", topic="二分探索", raw_transcript="二分探索", auto_sent=True, stt_latency_ms=-1
        )


class TestIntakeAnswersTopic:
    def test_topic_limit_matches_the_normalized_topic_length(self) -> None:
        from graph.intake_card import MAX_TOPIC_LENGTH
        from schemas.intake_card import MAX_TOPIC_ANSWER_LENGTH

        assert MAX_TOPIC_ANSWER_LENGTH == MAX_TOPIC_LENGTH

    def test_topic_defaults_to_empty_and_rejects_overlong_values(self) -> None:
        import pytest
        from pydantic import ValidationError

        from schemas.intake_card import MAX_TOPIC_ANSWER_LENGTH, IntakeAnswers

        assert IntakeAnswers().topic == ""
        with pytest.raises(ValidationError):
            IntakeAnswers(topic="あ" * (MAX_TOPIC_ANSWER_LENGTH + 1))


@pytest.mark.parametrize("answer", ["accept", "decline", None])
def test_user_message_accepts_a_topic_correction_answer(answer: str | None) -> None:
    payload: dict[str, object] = {"type": "user_message", "content": "はい", "client_message_id": str(uuid4())}
    if answer is not None:
        payload["topic_correction_answer"] = answer

    msg = _adapter.validate_python(payload)

    assert isinstance(msg, UserMessage)
    assert msg.topic_correction_answer == answer


def test_user_message_rejects_an_unknown_topic_correction_answer() -> None:
    with pytest.raises(ValidationError):
        _adapter.validate_python(
            {
                "type": "user_message",
                "content": "はい",
                "client_message_id": str(uuid4()),
                "topic_correction_answer": "maybe",
            }
        )


def test_topic_correction_question_message_has_its_type() -> None:
    message = TopicCorrectionQuestionMessage.model_validate(
        {"content": "変更しますか？", "card": {"previous_topic": "A", "new_topic": "B"}}
    )

    assert message.type == "topic_correction_question"


class TestStartReviewFocus:
    def test_focus_aspect_ids_are_optional(self) -> None:
        msg = _adapter.validate_python({"type": "start_review", "note_id": str(uuid4())})
        assert isinstance(msg, StartReviewMessage)
        assert msg.focus_aspect_ids is None

    def test_accepts_selected_ids_and_an_empty_selection(self) -> None:
        for ids in (["a1", "a1-2"], []):
            msg = _adapter.validate_python({"type": "start_review", "note_id": str(uuid4()), "focus_aspect_ids": ids})
            assert isinstance(msg, StartReviewMessage)
            assert msg.focus_aspect_ids == ids

    def test_rejects_too_many_ids(self) -> None:
        with pytest.raises(ValidationError):
            _adapter.validate_python(
                {"type": "start_review", "note_id": str(uuid4()), "focus_aspect_ids": [f"a{i}" for i in range(21)]}
            )


def test_session_ended_defaults_to_not_skipped() -> None:
    assert SessionEndedMessage().model_dump(mode="json") == {
        "type": "session_ended",
        "session_id": None,
        "note_skipped": False,
    }


def test_assistant_message_end_has_no_confirmation_by_default() -> None:
    assert AssistantMessageEnd().end_confirmation is None
