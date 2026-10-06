from typing import Protocol


class EmbeddingError(Exception):
    pass


class Embedder(Protocol):
    model: str

    async def embed(self, text: str) -> list[float]: ...
