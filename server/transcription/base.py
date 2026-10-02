from typing import Protocol


class TranscriptionError(Exception):
    pass


class Transcriber(Protocol):
    model: str

    async def transcribe(self, audio: bytes, mime_type: str) -> str: ...
