from functools import lru_cache

from openai import AsyncOpenAI

from core import config
from transcription.base import Transcriber, TranscriptionError
from transcription.openai_transcriber import OpenAITranscriber


@lru_cache(maxsize=1)
def get_transcriber() -> Transcriber:
    client = AsyncOpenAI(timeout=config.TRANSCRIPTION_TIMEOUT_SECONDS, max_retries=config.TRANSCRIPTION_MAX_RETRIES)
    return OpenAITranscriber(client, config.TRANSCRIPTION_MODEL, config.TRANSCRIPTION_LANGUAGE)


__all__ = ["Transcriber", "TranscriptionError", "get_transcriber"]
