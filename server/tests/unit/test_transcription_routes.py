from collections.abc import Iterator
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.routing import APIRoute
from starlette.datastructures import Headers

from api.routes.transcription import create_transcription
from core import config
from transcription import TranscriptionError

_USER_ID = "user-123"
_WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64
_MP4 = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 64


class _FakeTranscriber:
    model = "fake-transcribe"

    def __init__(self, text: str = "二分探索は半分に絞る", error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.calls: list[tuple[bytes, str]] = []

    async def transcribe(self, audio: bytes, mime_type: str) -> str:
        self.calls.append((audio, mime_type))
        if self.error is not None:
            raise self.error
        return self.text


def _upload(data: bytes, content_type: str = "audio/webm") -> UploadFile:
    return UploadFile(file=BytesIO(data), filename="recording", headers=Headers({"content-type": content_type}))


@pytest.fixture
def repos() -> Iterator[SimpleNamespace]:
    with (
        patch(
            "api.routes.transcription.dialogue_session_repository.find_by_id",
            new=AsyncMock(return_value={"id": uuid4()}),
        ) as find_session,
        patch(
            "api.routes.transcription.transcription_usage_repository.count_today_by_user",
            new=AsyncMock(return_value=0),
        ) as count_today,
        patch(
            "api.routes.transcription.transcription_usage_repository.insert",
            new=AsyncMock(),
        ) as insert_usage,
    ):
        yield SimpleNamespace(find_session=find_session, count_today=count_today, insert_usage=insert_usage)


async def _call(transcriber: _FakeTranscriber, audio: UploadFile, session_id: UUID | None = None) -> str:
    response = await create_transcription(
        current_user_id=_USER_ID,
        db=MagicMock(),
        transcriber=transcriber,
        dialogue_session_id=session_id or uuid4(),
        audio=audio,
    )
    return response.text


async def test_returns_the_transcript_and_records_usage(repos: SimpleNamespace) -> None:
    transcriber = _FakeTranscriber()
    session_id = uuid4()

    text = await _call(transcriber, _upload(_WEBM), session_id)

    assert text == "二分探索は半分に絞る"
    assert transcriber.calls == [(_WEBM, "audio/webm")]
    repos.count_today.assert_awaited_once()
    assert repos.count_today.await_args.args[1:] == (_USER_ID, config.REVIEW_TIMEZONE)
    repos.insert_usage.assert_awaited_once()
    assert repos.insert_usage.await_args.args[1:] == (_USER_ID, session_id, len(_WEBM), "fake-transcribe")


async def test_accepts_content_type_with_codec_parameters(repos: SimpleNamespace) -> None:
    transcriber = _FakeTranscriber()

    await _call(transcriber, _upload(_WEBM, "audio/webm;codecs=opus"))

    assert transcriber.calls == [(_WEBM, "audio/webm")]


async def test_accepts_mp4_from_safari(repos: SimpleNamespace) -> None:
    transcriber = _FakeTranscriber()

    await _call(transcriber, _upload(_MP4, "audio/mp4"))

    assert transcriber.calls == [(_MP4, "audio/mp4")]


async def test_rejects_a_session_the_user_does_not_own(repos: SimpleNamespace) -> None:
    repos.find_session.return_value = None
    transcriber = _FakeTranscriber()

    with pytest.raises(HTTPException) as exc_info:
        await _call(transcriber, _upload(_WEBM))

    assert exc_info.value.status_code == 404
    assert transcriber.calls == []


async def test_rejects_empty_audio(repos: SimpleNamespace) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await _call(_FakeTranscriber(), _upload(b""))

    assert exc_info.value.status_code == 400


async def test_rejects_audio_over_the_size_limit(repos: SimpleNamespace) -> None:
    oversized = _WEBM + b"\x00" * config.MAX_AUDIO_BYTES

    with pytest.raises(HTTPException) as exc_info:
        await _call(_FakeTranscriber(), _upload(oversized))

    assert exc_info.value.status_code == 413


async def test_rejects_unsupported_formats(repos: SimpleNamespace) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await _call(_FakeTranscriber(), _upload(b"OggS" + b"\x00" * 64, "audio/ogg"))

    assert exc_info.value.status_code == 415


async def test_rejects_content_that_does_not_match_the_declared_type(repos: SimpleNamespace) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await _call(_FakeTranscriber(), _upload(_WEBM, "audio/mp4"))

    assert exc_info.value.status_code == 415


async def test_rejects_once_the_daily_limit_is_reached(repos: SimpleNamespace) -> None:
    repos.count_today.return_value = config.DAILY_TRANSCRIPTION_LIMIT
    transcriber = _FakeTranscriber()

    with pytest.raises(HTTPException) as exc_info:
        await _call(transcriber, _upload(_WEBM))

    assert exc_info.value.status_code == 429
    assert transcriber.calls == []
    repos.insert_usage.assert_not_awaited()


async def test_reports_a_failed_transcription_without_recording_usage(repos: SimpleNamespace) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await _call(_FakeTranscriber(error=TranscriptionError("boom")), _upload(_WEBM))

    assert exc_info.value.status_code == 502
    repos.insert_usage.assert_not_awaited()


async def test_returns_an_empty_transcript_for_silence(repos: SimpleNamespace) -> None:
    assert await _call(_FakeTranscriber(text=""), _upload(_WEBM)) == ""


def test_router_is_registered() -> None:
    from main import app

    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    assert "/api/transcriptions" in paths
