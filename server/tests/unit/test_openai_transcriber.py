from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest

from core import config
from transcription import TranscriptionError, get_transcriber
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


def test_client_has_a_bounded_timeout_and_retry_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_transcriber.cache_clear()
    try:
        client = get_transcriber()._client  # type: ignore[attr-defined]
    finally:
        get_transcriber.cache_clear()

    assert client.timeout == config.TRANSCRIPTION_TIMEOUT_SECONDS
    assert client.max_retries == config.TRANSCRIPTION_MAX_RETRIES


async def test_passes_the_prompt_when_given() -> None:
    fake = _FakeTranscriptions(text="以上")
    await _transcriber(fake).transcribe(b"RIFF....WAVE", "audio/wav", prompt="「以上」で締めくくります")
    assert fake.calls[0]["prompt"] == "「以上」で締めくくります"
    assert fake.calls[0]["file"][0] == "audio.wav"


async def test_omits_the_prompt_when_absent() -> None:
    fake = _FakeTranscriptions(text="以上")
    await _transcriber(fake).transcribe(b"\x1a\x45\xdf\xa3", "audio/webm")
    assert "prompt" not in fake.calls[0]
