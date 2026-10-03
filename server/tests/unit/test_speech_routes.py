import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from fastapi.testclient import TestClient

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

    def __init__(self, audio: bytes = b"mp3", error: Exception | None = None, pool: _FakePool | None = None) -> None:
        self.audio = audio
        self.error = error
        self.pool = pool
        self.calls: list[str] = []
        self.connections_held_during_call: int | None = None

    async def synthesize(self, text: str) -> bytes:
        self.calls.append(text)
        if self.pool is not None:
            self.connections_held_during_call = self.pool.held
        if self.error is not None:
            raise self.error
        return self.audio


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
    ):
        yield SimpleNamespace(pool=pool, find_session=find_session, used=used, insert_usage=insert_usage)


async def _call(synthesizer: _FakeSynthesizer, text: str = "二分探索は半分に絞ります。") -> Response:
    return await create_speech(
        body=SpeechRequest(text=text, dialogue_session_id=uuid4()),
        current_user_id=_USER_ID,
        synthesizer=synthesizer,
    )


async def test_returns_mp3_audio_and_records_the_characters(repos: SimpleNamespace) -> None:
    synthesizer = _FakeSynthesizer(audio=b"mp3-bytes")

    response = await _call(synthesizer, "  二分探索です。  ")

    assert response.body == b"mp3-bytes"
    assert response.media_type == "audio/mpeg"
    assert synthesizer.calls == ["二分探索です。"]
    args = repos.insert_usage.await_args.args
    assert args[1] == _USER_ID
    assert args[3:] == (len("二分探索です。"), "fake-tts")


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
