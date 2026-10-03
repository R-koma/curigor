from openai import AsyncOpenAI, OpenAIError

from speech.base import SpeechError


class OpenAISynthesizer:
    def __init__(self, client: AsyncOpenAI, model: str, voice: str, instructions: str) -> None:
        self._client = client
        self.model = model
        self._voice = voice
        self._instructions = instructions

    async def synthesize(self, text: str) -> bytes:
        try:
            response = await self._client.audio.speech.create(
                model=self.model,
                voice=self._voice,
                input=text,
                instructions=self._instructions,
                response_format="mp3",
            )
        except OpenAIError as exc:
            raise SpeechError("speech request failed") from exc
        return response.content
