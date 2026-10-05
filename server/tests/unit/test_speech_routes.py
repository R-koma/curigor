import logging
from collections.abc import AsyncGenerator, AsyncIterator, Iterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.routes.speech import create_speech
from core import config
from schemas.speech import SpeechRequest
from speech import SpeechError

_USER_ID = "user-123"


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


class _FakeSynthesizer:
    model = "fake-tts"

    def __init__(
        self, chunks: list[bytes] | None = None, error: Exception | None = None, pool: _FakePool | None = None
    ) -> None:
        self.chunks = chunks if chunks is not None else [b"pc", b"m!"]
        self.error = error
        self.pool = pool
        self.calls: list[tuple[str, float]] = []
        self.connections_held_during_call: int | None = None
        self.closed = False

    async def stream(self, text: str, speed: float) -> AsyncGenerator[bytes]:
        self.calls.append((text, speed))
        if self.pool is not None:
            self.connections_held_during_call = self.pool.held
        if self.error is not None:
            raise self.error
        try:
            for chunk in self.chunks:
                yield chunk
        finally:
            self.closed = True


@pytest.fixture
def repos() -> Iterator[SimpleNamespace]:
    pool = _FakePool()
    with (
        patch("api.routes.speech.get_pool", new=AsyncMock(return_value=pool)),
        patch(
            "api.routes.speech.dialogue_session_repository.find_by_id", new=AsyncMock(return_value={"id": uuid4()})
        ) as find_session,
        patch("api.routes.speech.speech_usage_repository.sum_today_by_user", new=AsyncMock(return_value=0)) as used,
        patch("api.routes.speech.speech_usage_repository.insert", new=AsyncMock()) as insert_usage,
        patch("api.routes.speech.start_speech_trace", return_value=MagicMock()) as trace,
    ):
        yield SimpleNamespace(pool=pool, find_session=find_session, used=used, insert_usage=insert_usage, trace=trace)


async def _call(
    synthesizer: _FakeSynthesizer, text: str = "二分探索は半分に絞ります。", speed: float = 1.0
) -> StreamingResponse:
    return await create_speech(
        body=SpeechRequest(text=text, dialogue_session_id=uuid4(), speed=speed),
        current_user_id=_USER_ID,
        synthesizer=synthesizer,
    )


async def _body(response: Response) -> bytes:
    assert isinstance(response, StreamingResponse)
    return b"".join([chunk async for chunk in response.body_iterator])  # type: ignore[misc]


async def test_streams_pcm_and_records_the_characters_after_the_stream(repos: SimpleNamespace) -> None:
    synthesizer = _FakeSynthesizer(chunks=[b"ab", b"cd"])

    response = await _call(synthesizer, "  二分探索です。  ", speed=1.25)
    repos.insert_usage.assert_awaited_once()
    body = await _body(response)
    repos.insert_usage.assert_awaited_once()

    assert body == b"abcd"
    assert response.media_type == "application/octet-stream"
    assert synthesizer.calls == [("二分探索です。", 1.25)]
    args = repos.insert_usage.await_args.args
    assert args[1] == _USER_ID
    assert args[3:] == (len("二分探索です。"), "fake-tts")
    repos.trace.return_value.finish.assert_called_once_with(4)


async def test_returns_502_when_the_synthesizer_fails_before_the_first_chunk(repos: SimpleNamespace) -> None:
    with pytest.raises(HTTPException) as exc:
        await _call(_FakeSynthesizer(error=SpeechError("boom")))
    assert exc.value.status_code == 502
    repos.insert_usage.assert_not_awaited()


async def test_records_usage_and_closes_the_stream_even_if_the_body_never_starts(repos: SimpleNamespace) -> None:
    synthesizer = _FakeSynthesizer(chunks=[b"ab", b"cd"])

    response = await _call(synthesizer)
    assert response.background is not None
    await response.background()

    repos.insert_usage.assert_awaited_once()
    assert synthesizer.closed


async def test_mid_stream_speech_error_aborts_the_body_and_records_usage_once(repos: SimpleNamespace) -> None:
    class _Failing(_FakeSynthesizer):
        async def stream(self, text: str, speed: float) -> AsyncGenerator[bytes]:
            yield b"ab"
            raise SpeechError("boom")

    response = await _call(_Failing())
    iterator = cast(AsyncGenerator[bytes], response.body_iterator)

    assert await anext(iterator) == b"ab"
    with pytest.raises(SpeechError):
        await anext(iterator)
    repos.trace.return_value.finish.assert_called_once_with(2)
    repos.insert_usage.assert_awaited_once()


async def test_records_usage_even_when_the_client_disconnects_mid_stream(repos: SimpleNamespace) -> None:
    response = await _call(_FakeSynthesizer(chunks=[b"ab", b"cd"]))
    iterator = cast(AsyncGenerator[bytes], response.body_iterator)
    await anext(iterator)
    await iterator.aclose()

    repos.insert_usage.assert_awaited_once()


def test_rejects_unsupported_speed() -> None:
    with pytest.raises(ValidationError):
        SpeechRequest(text="あ", dialogue_session_id=uuid4(), speed=2.0)


def test_accepts_the_integer_default_speed_sent_by_the_client() -> None:
    sid = uuid4()
    one = SpeechRequest.model_validate_json(f'{{"text":"あ","dialogue_session_id":"{sid}","speed":1}}')
    quarter = SpeechRequest.model_validate_json(f'{{"text":"あ","dialogue_session_id":"{sid}","speed":1.25}}')
    assert one.speed == 1.0
    assert quarter.speed == 1.25
    with pytest.raises(ValidationError):
        SpeechRequest.model_validate_json(f'{{"text":"あ","dialogue_session_id":"{sid}","speed":2}}')


async def test_rejects_blank_text(repos: SimpleNamespace) -> None:
    with pytest.raises(HTTPException) as exc:
        await _call(_FakeSynthesizer(), "   \n")

    assert exc.value.status_code == 400
    repos.insert_usage.assert_not_awaited()


async def test_rejects_text_over_the_limit(repos: SimpleNamespace) -> None:
    synthesizer = _FakeSynthesizer()

    with pytest.raises(HTTPException) as exc:
        await _call(synthesizer, "あ" * (config.MAX_SPEECH_CHARS + 1))

    assert exc.value.status_code == 400
    assert synthesizer.calls == []


async def test_unknown_session_is_404(repos: SimpleNamespace) -> None:
    repos.find_session.return_value = None
    synthesizer = _FakeSynthesizer()

    with pytest.raises(HTTPException) as exc:
        await _call(synthesizer)

    assert exc.value.status_code == 404
    assert synthesizer.calls == []


async def test_daily_limit_is_429(repos: SimpleNamespace) -> None:
    repos.used.return_value = config.DAILY_SPEECH_CHAR_LIMIT
    synthesizer = _FakeSynthesizer()

    with pytest.raises(HTTPException) as exc:
        await _call(synthesizer)

    assert exc.value.status_code == 429
    assert synthesizer.calls == []


async def test_synthesis_failure_is_502_and_not_recorded(
    repos: SimpleNamespace, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)

    with pytest.raises(HTTPException) as exc:
        await _call(_FakeSynthesizer(error=SpeechError("boom")))

    assert exc.value.status_code == 502
    repos.insert_usage.assert_not_awaited()


async def test_releases_the_connection_before_synthesizing(repos: SimpleNamespace) -> None:
    synthesizer = _FakeSynthesizer(pool=repos.pool)

    await _call(synthesizer)

    assert synthesizer.connections_held_during_call == 0


def test_route_requires_authentication() -> None:
    from main import app

    response = TestClient(app).post("/api/speech", json={"text": "こんにちは", "dialogue_session_id": str(uuid4())})

    assert response.status_code in (401, 403)
