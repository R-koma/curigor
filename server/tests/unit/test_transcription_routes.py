import logging
import struct
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from api.dependencies import get_consented_user
from api.routes.transcription import create_transcription, format_transcription
from core import config
from schemas.transcription import TranscriptFormatRequest
from services.transcript_format import TranscriptFormatError
from transcription import TranscriptionError, get_transcriber

_USER_ID = "user-123"
_USAGE_ID = uuid4()
_WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64
_MP4 = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 64


class _FakePool:
    def __init__(self) -> None:
        self.held = 0

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[MagicMock]:
        self.held += 1
        try:
            yield MagicMock()
        finally:
            self.held -= 1


class _FakeTranscriber:
    model = "fake-transcribe"

    def __init__(
        self, text: str = "二分探索は半分に絞る", error: Exception | None = None, pool: _FakePool | None = None
    ) -> None:
        self.text = text
        self.error = error
        self.pool = pool
        self.calls: list[tuple[bytes, str]] = []
        self.prompts: list[str | None] = []
        self.keywords: list[list[str] | None] = []
        self.connections_held_during_call: int | None = None

    async def transcribe(
        self, audio: bytes, mime_type: str, prompt: str | None = None, keywords: list[str] | None = None
    ) -> str:
        self.calls.append((audio, mime_type))
        self.prompts.append(prompt)
        self.keywords.append(keywords)
        if self.pool is not None:
            self.connections_held_during_call = self.pool.held
        if self.error is not None:
            raise self.error
        return self.text


def _upload(data: bytes, content_type: str = "audio/webm") -> UploadFile:
    return UploadFile(file=BytesIO(data), filename="recording", headers=Headers({"content-type": content_type}))


@pytest.fixture
def repos() -> Iterator[SimpleNamespace]:
    pool = _FakePool()
    with (
        patch("api.routes.transcription.get_pool", new=AsyncMock(return_value=pool)),
        patch(
            "api.routes.transcription.dialogue_session_repository.find_by_id",
            new=AsyncMock(return_value={"id": uuid4(), "topic": "二分探索"}),
        ) as find_session,
        patch(
            "api.routes.transcription.dialogue_session_repository.find_transcription_keywords",
            new=AsyncMock(return_value=(None, None)),
        ) as find_keywords,
        patch(
            "api.routes.transcription.transcription_usage_repository.reserve",
            new=AsyncMock(return_value=_USAGE_ID),
        ) as reserve_usage,
        patch(
            "api.routes.transcription.transcription_usage_repository.cancel",
            new=AsyncMock(),
        ) as cancel_usage,
    ):
        yield SimpleNamespace(
            pool=pool,
            find_session=find_session,
            find_keywords=find_keywords,
            reserve_usage=reserve_usage,
            cancel_usage=cancel_usage,
        )


async def _call(
    transcriber: _FakeTranscriber, audio: UploadFile, session_id: UUID | None = None, prompt: str | None = None
) -> str:
    response = await create_transcription(
        current_user_id=_USER_ID,
        transcriber=transcriber,
        dialogue_session_id=session_id or uuid4(),
        audio=audio,
        prompt=prompt,
    )
    return response.text


async def test_passes_the_sessions_keywords(repos: SimpleNamespace) -> None:
    repos.find_keywords.return_value = (["二分探索", "計算量", "O(log n)"], "abc")
    transcriber = _FakeTranscriber()

    await _call(transcriber, _upload(_WEBM))

    assert transcriber.keywords == [["二分探索", "計算量", "O(log n)"]]


async def test_falls_back_to_the_topic_before_keywords_are_ready(repos: SimpleNamespace) -> None:
    transcriber = _FakeTranscriber()

    await _call(transcriber, _upload(_WEBM))

    assert transcriber.keywords == [["二分探索"]]


async def test_returns_the_transcript_and_keeps_the_reservation(repos: SimpleNamespace) -> None:
    transcriber = _FakeTranscriber()
    session_id = uuid4()

    text = await _call(transcriber, _upload(_WEBM), session_id)

    assert text == "二分探索は半分に絞る"
    assert transcriber.calls == [(_WEBM, "audio/webm")]
    repos.reserve_usage.assert_awaited_once()
    assert repos.reserve_usage.await_args.args[1:] == (
        _USER_ID,
        session_id,
        len(_WEBM),
        len(_WEBM) / 8000,
        "fake-transcribe",
        config.REVIEW_TIMEZONE,
        config.DAILY_TRANSCRIPTION_SECONDS,
    )
    repos.cancel_usage.assert_not_awaited()


async def test_reserves_before_transcribing(repos: SimpleNamespace) -> None:
    order: list[str] = []

    def reserve(*_: object) -> UUID:
        order.append("reserve")
        return _USAGE_ID

    repos.reserve_usage.side_effect = reserve

    class _Ordered(_FakeTranscriber):
        async def transcribe(
            self, audio: bytes, mime_type: str, prompt: str | None = None, keywords: list[str] | None = None
        ) -> str:
            order.append("transcribe")
            return "ok"

    await _call(_Ordered(), _upload(_WEBM))

    assert order == ["reserve", "transcribe"]


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
    repos.reserve_usage.assert_not_awaited()


async def test_rejects_empty_audio(repos: SimpleNamespace) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await _call(_FakeTranscriber(), _upload(b""))

    assert exc_info.value.status_code == 400
    repos.reserve_usage.assert_not_awaited()


async def test_rejects_audio_over_the_size_limit(repos: SimpleNamespace) -> None:
    oversized = _WEBM + b"\x00" * config.MAX_AUDIO_BYTES

    with pytest.raises(HTTPException) as exc_info:
        await _call(_FakeTranscriber(), _upload(oversized))

    assert exc_info.value.status_code == 413
    repos.reserve_usage.assert_not_awaited()


async def test_rejects_unsupported_formats(repos: SimpleNamespace) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await _call(_FakeTranscriber(), _upload(b"OggS" + b"\x00" * 64, "audio/ogg"))

    assert exc_info.value.status_code == 415
    repos.reserve_usage.assert_not_awaited()


async def test_rejects_content_that_does_not_match_the_declared_type(repos: SimpleNamespace) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await _call(_FakeTranscriber(), _upload(_WEBM, "audio/mp4"))

    assert exc_info.value.status_code == 415


async def test_rejects_once_the_daily_limit_is_reached(repos: SimpleNamespace) -> None:
    repos.reserve_usage.return_value = None
    transcriber = _FakeTranscriber()

    with pytest.raises(HTTPException) as exc_info:
        await _call(transcriber, _upload(_WEBM))

    assert exc_info.value.status_code == 429
    assert transcriber.calls == []
    repos.cancel_usage.assert_not_awaited()


async def test_reports_a_failed_transcription_and_cancels_the_reservation(repos: SimpleNamespace) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await _call(_FakeTranscriber(error=TranscriptionError("boom")), _upload(_WEBM))

    assert exc_info.value.status_code == 502
    repos.cancel_usage.assert_awaited_once()
    assert repos.cancel_usage.await_args.args[1:] == (_USAGE_ID,)


async def test_cancels_the_reservation_when_the_transcriber_raises_unexpectedly(repos: SimpleNamespace) -> None:
    with pytest.raises(RuntimeError):
        await _call(_FakeTranscriber(error=RuntimeError("boom")), _upload(_WEBM))

    repos.cancel_usage.assert_awaited_once()
    assert repos.cancel_usage.await_args.args[1:] == (_USAGE_ID,)


async def test_releases_the_connection_while_transcribing(repos: SimpleNamespace) -> None:
    transcriber = _FakeTranscriber(pool=repos.pool)

    await _call(transcriber, _upload(_WEBM))

    assert transcriber.connections_held_during_call == 0
    assert repos.pool.held == 0


async def test_logs_why_a_transcription_failed(repos: SimpleNamespace, caplog: pytest.LogCaptureFixture) -> None:
    failure = TranscriptionError("transcription request failed")

    with caplog.at_level(logging.WARNING, logger="api.routes.transcription"), pytest.raises(HTTPException):
        await _call(_FakeTranscriber(error=failure), _upload(_WEBM))

    assert any(
        record.getMessage() == "Transcription failed" and record.exc_info is not None for record in caplog.records
    )


async def test_transcribes_before_a_session_exists(repos: SimpleNamespace) -> None:
    transcriber = _FakeTranscriber()

    response = await create_transcription(
        current_user_id=_USER_ID, transcriber=transcriber, audio=_upload(_WEBM), dialogue_session_id=None
    )

    assert response.text == "二分探索は半分に絞る"
    repos.find_session.assert_not_awaited()
    assert transcriber.keywords == [None]
    assert repos.reserve_usage.await_args.args[1:3] == (_USER_ID, None)


async def test_daily_limit_applies_before_a_session_exists(repos: SimpleNamespace) -> None:
    repos.reserve_usage.return_value = None
    transcriber = _FakeTranscriber()

    with pytest.raises(HTTPException) as exc_info:
        await create_transcription(
            current_user_id=_USER_ID, transcriber=transcriber, audio=_upload(_WEBM), dialogue_session_id=None
        )

    assert exc_info.value.status_code == 429
    assert transcriber.calls == []


def _wav_bytes(samples: int, rate: int = 16000) -> bytes:
    data_size = samples * 2
    header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", data_size)
    return header + b"\x00" * data_size


async def test_accepts_wav_and_reserves_its_duration(repos: SimpleNamespace) -> None:
    transcriber = _FakeTranscriber()
    session_id = uuid4()
    wav = _wav_bytes(24000)

    await _call(transcriber, _upload(wav, "audio/wav"), session_id)

    assert transcriber.calls == [(wav, "audio/wav")]
    assert repos.reserve_usage.await_args.args[1:6] == (_USER_ID, session_id, len(wav), 1.5, "fake-transcribe")


async def test_rejects_wav_with_an_unsupported_header(repos: SimpleNamespace) -> None:
    stereo = bytearray(_wav_bytes(160))
    stereo[22] = 2
    with pytest.raises(HTTPException) as exc:
        await _call(_FakeTranscriber(), _upload(bytes(stereo), "audio/wav"))
    assert exc.value.status_code == 415
    repos.reserve_usage.assert_not_awaited()


async def test_passes_the_prompt_to_the_transcriber(repos: SimpleNamespace) -> None:
    transcriber = _FakeTranscriber()
    await _call(transcriber, _upload(_WEBM), prompt="「以上」で締めくくります")
    assert transcriber.prompts == ["「以上」で締めくくります"]


async def test_returns_an_empty_transcript_for_silence(repos: SimpleNamespace) -> None:
    assert await _call(_FakeTranscriber(text=""), _upload(_WEBM)) == ""


def test_router_is_registered() -> None:
    from main import app

    assert "/api/transcriptions" in app.openapi()["paths"]


@pytest.fixture
def client(repos: SimpleNamespace) -> Iterator[TestClient]:
    from main import app

    app.dependency_overrides[get_consented_user] = lambda: _USER_ID
    app.dependency_overrides[get_transcriber] = lambda: _FakeTranscriber()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_accepts_the_multipart_request_a_browser_sends(client: TestClient) -> None:
    response = client.post(
        "/api/transcriptions",
        data={"dialogue_session_id": str(uuid4())},
        files={"audio": ("recording.webm", _WEBM, "audio/webm;codecs=opus")},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "二分探索は半分に絞る"}


def test_rejects_a_malformed_session_id(client: TestClient) -> None:
    response = client.post(
        "/api/transcriptions",
        data={"dialogue_session_id": "not-a-uuid"},
        files={"audio": ("recording.webm", _WEBM, "audio/webm")},
    )

    assert response.status_code == 422


def test_rejects_a_request_without_audio(client: TestClient) -> None:
    response = client.post("/api/transcriptions", data={"dialogue_session_id": str(uuid4())})

    assert response.status_code == 422


def test_accepts_a_request_without_a_session_id(client: TestClient) -> None:
    response = client.post(
        "/api/transcriptions",
        files={"audio": ("recording.webm", _WEBM, "audio/webm;codecs=opus")},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "二分探索は半分に絞る"}


@pytest.fixture
def format_repos() -> Iterator[SimpleNamespace]:
    pool = _FakePool()
    held: list[int] = []

    async def fake_format(text: str, *, session_id: UUID, user_id: str) -> str:
        held.append(pool.held)
        return f"{text}。"

    with (
        patch("api.routes.transcription.get_pool", new=AsyncMock(return_value=pool)),
        patch(
            "api.routes.transcription.dialogue_session_repository.find_by_id",
            new=AsyncMock(return_value={"id": uuid4(), "topic": "二分探索"}),
        ) as find_session,
        patch("api.routes.transcription.format_transcript", new=AsyncMock(side_effect=fake_format)) as formatter,
    ):
        yield SimpleNamespace(find_session=find_session, formatter=formatter, held=held)


async def _format(text: str) -> str:
    response = await format_transcription(
        body=TranscriptFormatRequest(text=text, dialogue_session_id=uuid4()), current_user_id=_USER_ID
    )
    return response.text


@pytest.mark.parametrize("text", ["  \n ", "あ" * (config.MAX_TRANSCRIPT_FORMAT_CHARS + 1)])
async def test_format_rejects_empty_or_too_long_text(format_repos: SimpleNamespace, text: str) -> None:
    with pytest.raises(HTTPException) as exc:
        await _format(text)

    assert exc.value.status_code == 400
    assert exc.value.code == "transcript_text_invalid"  # type: ignore[attr-defined]
    format_repos.formatter.assert_not_awaited()


async def test_format_returns_404_for_a_session_that_is_not_the_users(format_repos: SimpleNamespace) -> None:
    format_repos.find_session.return_value = None

    with pytest.raises(HTTPException) as exc:
        await _format("スタックです")

    assert exc.value.status_code == 404
    format_repos.formatter.assert_not_awaited()


async def test_format_returns_502_when_formatting_fails(format_repos: SimpleNamespace) -> None:
    format_repos.formatter.side_effect = TranscriptFormatError("boom")

    with pytest.raises(HTTPException) as exc:
        await _format("スタックです")

    assert exc.value.status_code == 502
    assert exc.value.code == "transcript_format_failed"  # type: ignore[attr-defined]


async def test_format_returns_the_result_without_holding_a_connection(format_repos: SimpleNamespace) -> None:
    assert await _format("  スタックです ") == "スタックです。"
    assert format_repos.held == [0]
