from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest

from speech import SpeechError, get_synthesizer
from speech.openai_synthesizer import OpenAISynthesizer


class _FakeStreamingResponse:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    async def iter_bytes(self, chunk_size: int | None = None) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk


class _FakeSpeech:
    def __init__(self, chunks: list[bytes] | None = None, error: Exception | None = None) -> None:
        self.chunks = chunks or []
        self.error = error
        self.calls: list[dict[str, Any]] = []
        self.with_streaming_response = self

    @asynccontextmanager
    async def create(self, **kwargs: Any) -> AsyncIterator[_FakeStreamingResponse]:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        yield _FakeStreamingResponse(self.chunks)


def _synthesizer(fake: _FakeSpeech) -> OpenAISynthesizer:
    client = SimpleNamespace(audio=SimpleNamespace(speech=fake))
    return OpenAISynthesizer(client, model="gpt-4o-mini-tts", voice="coral", instructions="ゆっくり")  # type: ignore[arg-type]


async def _collect(synthesizer: OpenAISynthesizer, text: str, speed: float = 1.0) -> list[bytes]:
    return [chunk async for chunk in synthesizer.stream(text, speed)]


async def test_streams_pcm_with_model_voice_instructions_and_speed() -> None:
    fake = _FakeSpeech(chunks=[b"ab", b"cd"])

    chunks = await _collect(_synthesizer(fake), "二分探索は半分に絞ります。", 1.25)

    assert chunks == [b"ab", b"cd"]
    call = fake.calls[0]
    assert call["model"] == "gpt-4o-mini-tts"
    assert call["voice"] == "coral"
    assert call["input"] == "二分探索は半分に絞ります。"
    assert call["instructions"] == "ゆっくり"
    assert call["response_format"] == "pcm"
    assert call["speed"] == 1.25


async def test_wraps_openai_errors() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/audio/speech")
    fake = _FakeSpeech(error=openai.APIConnectionError(request=request))

    with pytest.raises(SpeechError):
        await _collect(_synthesizer(fake), "あ。")


def test_get_synthesizer_returns_a_cached_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_synthesizer.cache_clear()

    assert get_synthesizer() is get_synthesizer()
    assert get_synthesizer().model == "gpt-4o-mini-tts"
