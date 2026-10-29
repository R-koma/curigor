from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Literal

from aiobotocore.config import AioConfig
from aiobotocore.session import get_session
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client

_DELETE_BATCH_SIZE = 1000
_MISSING_KEY_CODES = {"NoSuchKey", "404"}


def _check_key(key: str) -> None:
    if not key or key.startswith("/") or ".." in key.split("/"):
        raise ValueError("Invalid storage key")


class S3ObjectStorage:
    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        addressing_style: Literal["virtual", "path", "auto"] = "virtual",
    ) -> None:
        self._bucket = bucket
        self._endpoint_url = endpoint_url
        self._region = region
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._config = AioConfig(signature_version="s3v4", s3={"addressing_style": addressing_style})
        self._session = get_session()

    @asynccontextmanager
    async def _client(self) -> AsyncIterator["S3Client"]:
        async with self._session.create_client(
            "s3",
            region_name=self._region,
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key_id,
            aws_secret_access_key=self._secret_access_key,
            config=self._config,
        ) as client:
            yield client

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        _check_key(key)
        async with self._client() as client:
            await client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    async def get(self, key: str) -> bytes:
        _check_key(key)
        async with self._client() as client:
            try:
                response = await client.get_object(Bucket=self._bucket, Key=key)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in _MISSING_KEY_CODES:
                    raise FileNotFoundError(key) from exc
                raise
            async with response["Body"] as stream:
                data: bytes = await stream.read()
                return data

    async def delete(self, key: str) -> None:
        _check_key(key)
        async with self._client() as client:
            await client.delete_object(Bucket=self._bucket, Key=key)

    async def delete_prefix(self, prefix: str) -> None:
        _check_key(prefix)
        prefix = prefix if prefix.endswith("/") else f"{prefix}/"
        async with self._client() as client:
            paginator = client.get_paginator("list_objects_v2")
            keys: list[str] = []
            async for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                keys.extend(obj["Key"] for obj in page.get("Contents", []))
            for start in range(0, len(keys), _DELETE_BATCH_SIZE):
                batch = keys[start : start + _DELETE_BATCH_SIZE]
                await client.delete_objects(
                    Bucket=self._bucket, Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True}
                )

    async def list_child_prefixes(self, prefix: str) -> list[str]:
        _check_key(prefix)
        prefix = prefix if prefix.endswith("/") else f"{prefix}/"
        names: list[str] = []
        async with self._client() as client:
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix, Delimiter="/"):
                for common in page.get("CommonPrefixes", []):
                    names.append(common["Prefix"][len(prefix) :].rstrip("/"))
        return names
