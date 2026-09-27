import base64
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from core import config
from schemas.websocket_message import ImageAttachment, IncomingMessage, StartLearningMessage, UserMessage

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
