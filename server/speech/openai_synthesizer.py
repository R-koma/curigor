from collections.abc import AsyncGenerator

from openai import AsyncOpenAI, OpenAIError

from speech.base import SpeechError

_CHUNK_BYTES = 4800


class OpenAISynthesizer:
    def __init__(self, client: AsyncOpenAI, model: str, voice: str, instructions: str) -> None:
        self._client = client
        self.model = model
        self._voice = voice
        self._instructions = instructions

    async def stream(self, text: str, speed: float) -> AsyncGenerator[bytes]:
        try:
            async with self._client.audio.speech.with_streaming_response.create(
                model=self.model,
                voice=self._voice,
                input=text,
                instructions=self._instructions,
                response_format="pcm",
                speed=speed,
            ) as response:
                async for chunk in response.iter_bytes(_CHUNK_BYTES):
                    yield chunk
        except OpenAIError as exc:
            raise SpeechError("speech request failed") from exc
