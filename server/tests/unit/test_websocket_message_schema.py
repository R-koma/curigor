import base64
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from core import config
from schemas.intake_card import IntakeAnswers, IntakeCard
from schemas.websocket_message import (
    ImageAttachment,
    IncomingMessage,
    IntakeQuestionMessage,
    StartLearningMessage,
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
