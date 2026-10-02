from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest

from transcription import TranscriptionError
from transcription.openai_transcriber import OpenAITranscriber


class _FakeTranscriptions:
    def __init__(self, text: str = "", error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(text=self.text)


def _transcriber(fake: _FakeTranscriptions) -> OpenAITranscriber:
    client = SimpleNamespace(audio=SimpleNamespace(transcriptions=fake))
    return OpenAITranscriber(client, model="gpt-transcribe", language="ja")  # type: ignore[arg-type]


async def test_sends_the_audio_with_model_and_language() -> None:
    fake = _FakeTranscriptions(text="二分探索は半分に絞る")

    text = await _transcriber(fake).transcribe(b"webm-bytes", "audio/webm")

    assert text == "二分探索は半分に絞る"
    call = fake.calls[0]
    assert call["model"] == "gpt-transcribe"
    assert call["file"] == ("audio.webm", b"webm-bytes", "audio/webm")
    assert call["response_format"] == "json"
    assert call["extra_body"] == {"languages": ["ja"]}


async def test_names_mp4_audio_with_the_mp4_extension() -> None:
    fake = _FakeTranscriptions(text="x")

    await _transcriber(fake).transcribe(b"mp4-bytes", "audio/mp4")

    assert fake.calls[0]["file"] == ("audio.mp4", b"mp4-bytes", "audio/mp4")


async def test_strips_surrounding_whitespace() -> None:
    fake = _FakeTranscriptions(text="  こんにちは\n")

    assert await _transcriber(fake).transcribe(b"x", "audio/webm") == "こんにちは"


async def test_wraps_api_errors() -> None:
    error = openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions"))
    fake = _FakeTranscriptions(error=error)

    with pytest.raises(TranscriptionError):
        await _transcriber(fake).transcribe(b"x", "audio/webm")


def test_exposes_the_model_name() -> None:
    assert _transcriber(_FakeTranscriptions()).model == "gpt-transcribe"
