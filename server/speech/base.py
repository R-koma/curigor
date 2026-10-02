from typing import Protocol


class SpeechError(Exception):
    pass


class Synthesizer(Protocol):
    model: str

    async def synthesize(self, text: str) -> bytes: ...
