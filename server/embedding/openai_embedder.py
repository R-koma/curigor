from openai import AsyncOpenAI, OpenAIError

from embedding.base import EmbeddingError


class OpenAIEmbedder:
    def __init__(self, client: AsyncOpenAI, model: str, dimensions: int) -> None:
        self._client = client
        self.model = model
        self._dimensions = dimensions

    async def embed(self, text: str) -> list[float]:
        try:
            result = await self._client.embeddings.create(model=self.model, input=text, dimensions=self._dimensions)
        except OpenAIError as exc:
            raise EmbeddingError("embedding request failed") from exc
        return list(result.data[0].embedding)
