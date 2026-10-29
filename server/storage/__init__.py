from functools import lru_cache
from typing import Literal
from uuid import UUID

from core import config
from storage.base import ObjectStorage
from storage.local import LocalObjectStorage
from storage.s3 import S3ObjectStorage


@lru_cache(maxsize=1)
def get_storage() -> ObjectStorage:
    backend = config.STORAGE_BACKEND
    if backend == "local":
        return LocalObjectStorage(config.LOCAL_STORAGE_DIR)
    if backend == "s3":
        return _s3_storage()
    raise ValueError(f"Unsupported STORAGE_BACKEND: {backend!r}")


def _s3_storage() -> S3ObjectStorage:
    if not (config.S3_BUCKET and config.S3_ACCESS_KEY_ID and config.S3_SECRET_ACCESS_KEY):
        raise ValueError("S3_BUCKET, S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY are required for STORAGE_BACKEND=s3")
    style: Literal["virtual", "path", "auto"]
    match config.S3_ADDRESSING_STYLE:
        case "virtual" | "path" | "auto" as matched:
            style = matched
        case other:
            raise ValueError(f"Unsupported S3_ADDRESSING_STYLE: {other!r}")
    return S3ObjectStorage(
        bucket=config.S3_BUCKET,
        endpoint_url=config.S3_ENDPOINT_URL,
        region=config.S3_REGION,
        access_key_id=config.S3_ACCESS_KEY_ID,
        secret_access_key=config.S3_SECRET_ACCESS_KEY,
        addressing_style=style,
    )


DIALOGUE_IMAGES_PREFIX = "dialogue_images/"
AVATARS_PREFIX = "avatars/"


def dialogue_image_prefix(session_id: UUID) -> str:
    return f"{DIALOGUE_IMAGES_PREFIX}{session_id}/"


def avatar_prefix(user_id: str) -> str:
    return f"{AVATARS_PREFIX}{user_id}/"


__all__ = [
    "AVATARS_PREFIX",
    "DIALOGUE_IMAGES_PREFIX",
    "ObjectStorage",
    "S3ObjectStorage",
    "avatar_prefix",
    "dialogue_image_prefix",
    "get_storage",
]
