from pathlib import Path

import pytest

from storage.local import LocalObjectStorage


async def test_put_then_get_roundtrips_bytes(tmp_path: Path) -> None:
    storage = LocalObjectStorage(tmp_path)
    await storage.put("a/b/c.png", b"hello", "image/png")

    assert await storage.get("a/b/c.png") == b"hello"


async def test_put_creates_nested_directories(tmp_path: Path) -> None:
    storage = LocalObjectStorage(tmp_path)
    await storage.put("dialogue_images/session/0.jpg", b"x", "image/jpeg")

    assert (tmp_path / "dialogue_images" / "session" / "0.jpg").read_bytes() == b"x"


async def test_delete_is_idempotent(tmp_path: Path) -> None:
    storage = LocalObjectStorage(tmp_path)
    await storage.put("k.png", b"x", "image/png")

    await storage.delete("k.png")
    await storage.delete("k.png")  # 既に無くても例外を出さない

    assert not (tmp_path / "k.png").exists()


@pytest.mark.parametrize("key", ["../escape.png", "a/../../escape.png"])
async def test_rejects_path_traversal(tmp_path: Path, key: str) -> None:
    storage = LocalObjectStorage(tmp_path)
    with pytest.raises(ValueError, match="Invalid storage key"):
        await storage.put(key, b"x", "image/png")


async def test_delete_prefix_removes_everything_under_it(tmp_path: Path) -> None:
    storage = LocalObjectStorage(tmp_path)
    await storage.put("dialogue_images/s1/m1/0.png", b"x", "image/png")
    await storage.put("dialogue_images/s1/m2/0.png", b"x", "image/png")
    await storage.put("dialogue_images/s2/m1/0.png", b"x", "image/png")

    await storage.delete_prefix("dialogue_images/s1/")

    assert not (tmp_path / "dialogue_images" / "s1").exists()
    assert (tmp_path / "dialogue_images" / "s2" / "m1" / "0.png").exists()


async def test_delete_prefix_succeeds_when_nothing_is_there(tmp_path: Path) -> None:
    await LocalObjectStorage(tmp_path).delete_prefix("dialogue_images/missing/")


@pytest.mark.parametrize("prefix", ["", "../", "dialogue_images/../../"])
async def test_delete_prefix_rejects_the_root_and_traversal(tmp_path: Path, prefix: str) -> None:
    with pytest.raises(ValueError, match="Invalid storage key"):
        await LocalObjectStorage(tmp_path).delete_prefix(prefix)


async def test_list_child_prefixes_returns_the_names_directly_under_it(tmp_path: Path) -> None:
    storage = LocalObjectStorage(tmp_path)
    await storage.put("dialogue_images/s1/m1/0.png", b"x", "image/png")
    await storage.put("dialogue_images/s2/m1/0.png", b"x", "image/png")
    await storage.put("dialogue_images/stray.png", b"x", "image/png")

    assert sorted(await storage.list_child_prefixes("dialogue_images/")) == ["s1", "s2"]


async def test_list_child_prefixes_is_empty_when_nothing_is_there(tmp_path: Path) -> None:
    assert await LocalObjectStorage(tmp_path).list_child_prefixes("dialogue_images/") == []


@pytest.mark.parametrize("prefix", ["../", "dialogue_images/../../"])
async def test_list_child_prefixes_rejects_traversal(tmp_path: Path, prefix: str) -> None:
    with pytest.raises(ValueError, match="Invalid storage key"):
        await LocalObjectStorage(tmp_path).list_child_prefixes(prefix)
