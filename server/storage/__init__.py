from functools import lru_cache
from uuid import UUID

from core import config
from storage.base import ObjectStorage
from storage.local import LocalObjectStorage


@lru_cache(maxsize=1)
def get_storage() -> ObjectStorage:
    backend = config.STORAGE_BACKEND
    if backend == "local":
        return LocalObjectStorage(config.LOCAL_STORAGE_DIR)
    raise ValueError(f"Unsupported STORAGE_BACKEND: {backend!r}")


def dialogue_image_prefix(session_id: UUID) -> str:
    return f"dialogue_images/{session_id}/"


__all__ = ["ObjectStorage", "dialogue_image_prefix", "get_storage"]
