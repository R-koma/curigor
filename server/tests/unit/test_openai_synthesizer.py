from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest

from speech import SpeechError, get_synthesizer
from speech.openai_synthesizer import OpenAISynthesizer


class _FakeSpeech:
    def __init__(self, audio: bytes = b"", error: Exception | None = None) -> None:
        self.audio = audio
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(content=self.audio)


def _synthesizer(fake: _FakeSpeech) -> OpenAISynthesizer:
    client = SimpleNamespace(audio=SimpleNamespace(speech=fake))
    return OpenAISynthesizer(client, model="gpt-4o-mini-tts", voice="coral", instructions="ゆっくり")  # type: ignore[arg-type]


async def test_sends_the_text_with_model_voice_and_instructions() -> None:
    fake = _FakeSpeech(audio=b"mp3-bytes")

    audio = await _synthesizer(fake).synthesize("二分探索は半分に絞ります。")

    assert audio == b"mp3-bytes"
    call = fake.calls[0]
    assert call["model"] == "gpt-4o-mini-tts"
    assert call["voice"] == "coral"
    assert call["input"] == "二分探索は半分に絞ります。"
    assert call["instructions"] == "ゆっくり"
    assert call["response_format"] == "mp3"


async def test_wraps_api_failures_in_speech_error() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/audio/speech")
    error = openai.APIConnectionError(request=request)

    with pytest.raises(SpeechError):
        await _synthesizer(_FakeSpeech(error=error)).synthesize("こんにちは")


def test_get_synthesizer_returns_a_cached_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_synthesizer.cache_clear()

    assert get_synthesizer() is get_synthesizer()
    assert get_synthesizer().model == "gpt-4o-mini-tts"
