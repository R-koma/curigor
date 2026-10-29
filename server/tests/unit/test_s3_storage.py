from collections.abc import AsyncIterator, Iterator
from uuid import uuid4

import pytest
import pytest_asyncio
from aiobotocore.session import get_session
from moto.server import ThreadedMotoServer

from storage import s3 as s3_module
from storage.s3 import S3ObjectStorage

_KEY_ID = "test-key"
_SECRET = "test-secret"  # noqa: S105
_REGION = "us-east-1"


@pytest.fixture(scope="module")
def s3_endpoint() -> Iterator[str]:
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    yield f"http://{host}:{port}"
    server.stop()


@pytest_asyncio.fixture
async def storage(s3_endpoint: str) -> AsyncIterator[S3ObjectStorage]:
    bucket = f"test-{uuid4().hex}"
    async with get_session().create_client(
        "s3",
        region_name=_REGION,
        endpoint_url=s3_endpoint,
        aws_access_key_id=_KEY_ID,
        aws_secret_access_key=_SECRET,
    ) as client:
        await client.create_bucket(Bucket=bucket)
    yield S3ObjectStorage(
        bucket=bucket,
        endpoint_url=s3_endpoint,
        region=_REGION,
        access_key_id=_KEY_ID,
        secret_access_key=_SECRET,
        addressing_style="path",
    )


async def test_put_then_get_roundtrips_bytes(storage: S3ObjectStorage) -> None:
    await storage.put("a/b/c.png", b"hello", "image/png")

    assert await storage.get("a/b/c.png") == b"hello"


async def test_get_raises_file_not_found_for_a_missing_key(storage: S3ObjectStorage) -> None:
    with pytest.raises(FileNotFoundError):
        await storage.get("missing.png")


async def test_delete_is_idempotent(storage: S3ObjectStorage) -> None:
    await storage.put("k.png", b"x", "image/png")

    await storage.delete("k.png")
    await storage.delete("k.png")

    with pytest.raises(FileNotFoundError):
        await storage.get("k.png")


@pytest.mark.parametrize("key", ["", "/abs.png", "../escape.png", "a/../../escape.png"])
async def test_rejects_invalid_keys(storage: S3ObjectStorage, key: str) -> None:
    with pytest.raises(ValueError, match="Invalid storage key"):
        await storage.put(key, b"x", "image/png")


async def test_delete_prefix_removes_everything_under_it(
    storage: S3ObjectStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(s3_module, "_DELETE_BATCH_SIZE", 2)
    for key in ("s1/m1/0.png", "s1/m1/1.png", "s1/m2/0.png", "s2/m1/0.png", "s10/m1/0.png"):
        await storage.put(f"dialogue_images/{key}", b"x", "image/png")

    await storage.delete_prefix("dialogue_images/s1")

    assert sorted(await storage.list_child_prefixes("dialogue_images/")) == ["s10", "s2"]


async def test_delete_prefix_succeeds_when_nothing_is_there(storage: S3ObjectStorage) -> None:
    await storage.delete_prefix("dialogue_images/missing/")


@pytest.mark.parametrize("prefix", ["", "../", "dialogue_images/../../"])
async def test_delete_prefix_rejects_the_root_and_traversal(storage: S3ObjectStorage, prefix: str) -> None:
    with pytest.raises(ValueError, match="Invalid storage key"):
        await storage.delete_prefix(prefix)


async def test_list_child_prefixes_returns_the_names_directly_under_it(storage: S3ObjectStorage) -> None:
    await storage.put("dialogue_images/s1/m1/0.png", b"x", "image/png")
    await storage.put("dialogue_images/s2/m1/0.png", b"x", "image/png")
    await storage.put("dialogue_images/stray.png", b"x", "image/png")

    assert sorted(await storage.list_child_prefixes("dialogue_images/")) == ["s1", "s2"]


async def test_list_child_prefixes_is_empty_when_nothing_is_there(storage: S3ObjectStorage) -> None:
    assert await storage.list_child_prefixes("dialogue_images/") == []
