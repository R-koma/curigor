from typing import Any

from openai import AsyncOpenAI, OpenAIError

from transcription.base import TranscriptionError

_EXTENSIONS = {"audio/webm": "webm", "audio/mp4": "mp4", "audio/wav": "wav"}


class OpenAITranscriber:
    def __init__(self, client: AsyncOpenAI, model: str, language: str) -> None:
        self._client = client
        self.model = model
        self._language = language

    async def transcribe(self, audio: bytes, mime_type: str, prompt: str | None = None) -> str:
        options: dict[str, Any] = {"prompt": prompt} if prompt else {}
        try:
            result = await self._client.audio.transcriptions.create(
                model=self.model,
                file=(f"audio.{_EXTENSIONS[mime_type]}", audio, mime_type),
                response_format="json",
                # openai 2.28 の SDK は gpt-transcribe の `languages` を引数に持たない
                extra_body={"languages": [self._language]},
                **options,
            )
        except OpenAIError as exc:
            raise TranscriptionError("transcription request failed") from exc
        return str(result.text).strip()
