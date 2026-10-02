from functools import lru_cache

from openai import AsyncOpenAI

from core import config
from transcription.base import Transcriber, TranscriptionError
from transcription.openai_transcriber import OpenAITranscriber


@lru_cache(maxsize=1)
def get_transcriber() -> Transcriber:
    return OpenAITranscriber(AsyncOpenAI(), config.TRANSCRIPTION_MODEL, config.TRANSCRIPTION_LANGUAGE)


__all__ = ["Transcriber", "TranscriptionError", "get_transcriber"]
