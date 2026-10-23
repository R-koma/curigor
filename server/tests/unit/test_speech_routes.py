import asyncio
import logging
from collections.abc import AsyncGenerator, AsyncIterator, Iterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

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
_USAGE_ID = uuid4()


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
        self, chunks: list[bytes] | None = None, error: BaseException | None = None, pool: _FakePool | None = None
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
        patch(
            "api.routes.speech.speech_usage_repository.reserve", new=AsyncMock(return_value=_USAGE_ID)
        ) as reserve_usage,
        patch("api.routes.speech.speech_usage_repository.cancel", new=AsyncMock()) as cancel_usage,
        patch("api.routes.speech.start_speech_trace", return_value=MagicMock()) as trace,
    ):
        yield SimpleNamespace(
            pool=pool, find_session=find_session, reserve_usage=reserve_usage, cancel_usage=cancel_usage, trace=trace
        )


async def _call(
    synthesizer: _FakeSynthesizer,
    text: str = "二分探索は半分に絞ります。",
    speed: float = 1.0,
    session_id: UUID | None = None,
) -> StreamingResponse:
    return await create_speech(
        body=SpeechRequest(text=text, dialogue_session_id=session_id or uuid4(), speed=speed),
        current_user_id=_USER_ID,
        synthesizer=synthesizer,
    )


async def _body(response: Response) -> bytes:
    assert isinstance(response, StreamingResponse)
    return b"".join([chunk async for chunk in response.body_iterator])  # type: ignore[misc]


async def test_streams_pcm_and_keeps_the_reservation(repos: SimpleNamespace) -> None:
    synthesizer = _FakeSynthesizer(chunks=[b"ab", b"cd"])
    session_id = uuid4()

    response = await _call(synthesizer, "  二分探索です。  ", speed=1.25, session_id=session_id)
    body = await _body(response)

    assert body == b"abcd"
    assert response.media_type == "application/octet-stream"
    assert synthesizer.calls == [("二分探索です。", 1.25)]
    repos.reserve_usage.assert_awaited_once()
    assert repos.reserve_usage.await_args.args[1:] == (
        _USER_ID,
        session_id,
        len("二分探索です。"),
        "fake-tts",
        config.REVIEW_TIMEZONE,
        config.DAILY_SPEECH_CHAR_LIMIT,
    )
    repos.cancel_usage.assert_not_awaited()
    repos.trace.return_value.finish.assert_called_once_with(4)


async def test_reserves_before_synthesizing(repos: SimpleNamespace) -> None:
    order: list[str] = []

    def reserve(*_: object) -> UUID:
        order.append("reserve")
        return _USAGE_ID

    repos.reserve_usage.side_effect = reserve

    class _Ordered(_FakeSynthesizer):
        async def stream(self, text: str, speed: float) -> AsyncGenerator[bytes]:
            order.append("synthesize")
            yield b"ab"

    await _body(await _call(_Ordered()))

    assert order == ["reserve", "synthesize"]


async def test_returns_502_and_cancels_the_reservation_when_the_synthesizer_fails_before_the_first_chunk(
    repos: SimpleNamespace,
) -> None:
    with pytest.raises(HTTPException) as exc:
        await _call(_FakeSynthesizer(error=SpeechError("boom")))
    assert exc.value.status_code == 502
    repos.cancel_usage.assert_awaited_once()
    assert repos.cancel_usage.await_args.args[1:] == (_USAGE_ID,)


async def test_keeps_the_reservation_when_the_request_is_cancelled_before_the_first_chunk(
    repos: SimpleNamespace,
) -> None:
    with pytest.raises(asyncio.CancelledError):
        await _call(_FakeSynthesizer(error=asyncio.CancelledError()))

    repos.cancel_usage.assert_not_awaited()
    repos.trace.return_value.finish.assert_called_once_with(0)


async def test_keeps_usage_and_closes_the_stream_even_if_the_body_never_starts(repos: SimpleNamespace) -> None:
    synthesizer = _FakeSynthesizer(chunks=[b"ab", b"cd"])

    response = await _call(synthesizer)
    assert response.background is not None
    await response.background()

    repos.cancel_usage.assert_not_awaited()
    assert synthesizer.closed


async def test_mid_stream_speech_error_aborts_the_body_and_keeps_usage(repos: SimpleNamespace) -> None:
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
    repos.cancel_usage.assert_not_awaited()


async def test_keeps_usage_even_when_the_client_disconnects_mid_stream(repos: SimpleNamespace) -> None:
    response = await _call(_FakeSynthesizer(chunks=[b"ab", b"cd"]))
    iterator = cast(AsyncGenerator[bytes], response.body_iterator)
    await anext(iterator)
    await iterator.aclose()

    repos.cancel_usage.assert_not_awaited()


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
    repos.reserve_usage.assert_not_awaited()


async def test_rejects_text_over_the_limit(repos: SimpleNamespace) -> None:
    synthesizer = _FakeSynthesizer()

    with pytest.raises(HTTPException) as exc:
        await _call(synthesizer, "あ" * (config.MAX_SPEECH_CHARS + 1))

    assert exc.value.status_code == 400
    assert synthesizer.calls == []
    repos.reserve_usage.assert_not_awaited()


async def test_unknown_session_is_404(repos: SimpleNamespace) -> None:
    repos.find_session.return_value = None
    synthesizer = _FakeSynthesizer()

    with pytest.raises(HTTPException) as exc:
        await _call(synthesizer)

    assert exc.value.status_code == 404
    assert synthesizer.calls == []
    repos.reserve_usage.assert_not_awaited()


async def test_daily_limit_is_429(repos: SimpleNamespace) -> None:
    repos.reserve_usage.return_value = None
    synthesizer = _FakeSynthesizer()

    with pytest.raises(HTTPException) as exc:
        await _call(synthesizer)

    assert exc.value.status_code == 429
    assert synthesizer.calls == []
    repos.cancel_usage.assert_not_awaited()


async def test_synthesis_failure_is_502_and_logged(repos: SimpleNamespace, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)

    with pytest.raises(HTTPException) as exc:
        await _call(_FakeSynthesizer(error=SpeechError("boom")))

    assert exc.value.status_code == 502
    assert any(record.getMessage() == "Speech synthesis failed" for record in caplog.records)


async def test_releases_the_connection_before_synthesizing(repos: SimpleNamespace) -> None:
    synthesizer = _FakeSynthesizer(pool=repos.pool)

    await _call(synthesizer)

    assert synthesizer.connections_held_during_call == 0


def test_route_requires_authentication() -> None:
    from main import app

    response = TestClient(app).post("/api/speech", json={"text": "こんにちは", "dialogue_session_id": str(uuid4())})

    assert response.status_code in (401, 403)
