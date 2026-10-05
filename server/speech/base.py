from collections.abc import AsyncGenerator
from typing import Protocol


class SpeechError(Exception):
    pass


class Synthesizer(Protocol):
    model: str

    def stream(self, text: str, speed: float) -> AsyncGenerator[bytes]: ...
