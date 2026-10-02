from functools import lru_cache

from openai import AsyncOpenAI

from core import config
from speech.base import SpeechError, Synthesizer
from speech.openai_synthesizer import OpenAISynthesizer


@lru_cache(maxsize=1)
def get_synthesizer() -> Synthesizer:
    client = AsyncOpenAI(timeout=config.SPEECH_TIMEOUT_SECONDS, max_retries=config.SPEECH_MAX_RETRIES)
    return OpenAISynthesizer(client, config.SPEECH_MODEL, config.SPEECH_VOICE, config.SPEECH_INSTRUCTIONS)


__all__ = ["SpeechError", "Synthesizer", "get_synthesizer"]
