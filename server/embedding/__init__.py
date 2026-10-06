from functools import lru_cache

from openai import AsyncOpenAI

from core import config
from embedding.base import Embedder, EmbeddingError
from embedding.openai_embedder import OpenAIEmbedder


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    client = AsyncOpenAI(timeout=config.EMBEDDING_TIMEOUT_SECONDS, max_retries=config.EMBEDDING_MAX_RETRIES)
    return OpenAIEmbedder(client, config.EMBEDDING_MODEL, config.EMBEDDING_DIMENSIONS)


__all__ = ["Embedder", "EmbeddingError", "get_embedder"]
