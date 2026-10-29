from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from core import config
from main import app
from storage import get_storage
from storage.local import LocalObjectStorage

pytestmark = pytest.mark.asyncio(loop_scope="session")

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
_JPEG = b"\xff\xd8\xff" + b"\x00" * 16
_GIF = b"GIF89a" + b"\x00" * 16


class Users:
    current = "avatar-user-a"


@pytest_asyncio.fixture(loop_scope="session")
async def client(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    storage = LocalObjectStorage(tmp_path)
    app.dependency_overrides[get_current_user] = lambda: Users.current
    app.dependency_overrides[get_storage] = lambda: storage
    Users.current = "avatar-user-a"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _upload(client: AsyncClient, data: bytes, name: str = "a.png") -> str:
    res = await client.put("/api/account/avatar", files={"file": (name, data, "image/png")})
    assert res.status_code == 200, res.text
    path: str = res.json()["path"]
    return path


async def test_uploaded_avatar_is_served_publicly_with_its_type(client: AsyncClient, tmp_path: Path) -> None:
    path = await _upload(client, _PNG)

    assert path.startswith("/api/avatars/avatar-user-a/")
    app.dependency_overrides.pop(get_current_user)
    res = await client.get(path)
    assert res.status_code == 200
    assert res.content == _PNG
    assert res.headers["content-type"] == "image/png"
    assert res.headers["x-content-type-options"] == "nosniff"
    assert "immutable" in res.headers["cache-control"]


async def test_detects_the_type_from_the_bytes(client: AsyncClient) -> None:
    path = await _upload(client, _JPEG, name="looks-like.png")

    assert path.endswith(".jpg")


async def test_a_new_upload_replaces_the_old_one(client: AsyncClient, tmp_path: Path) -> None:
    first = await _upload(client, _PNG)
    second = await _upload(client, _PNG)

    assert first != second
    assert (await client.get(first)).status_code == 404
    assert (await client.get(second)).status_code == 200
    assert len(list((tmp_path / "avatars" / "avatar-user-a").iterdir())) == 1


@pytest.mark.parametrize(
    ("data", "status", "code"),
    [
        (b"", 400, "avatar_empty"),
        (_GIF, 415, "unsupported_avatar_format"),
        (b"<svg></svg>", 415, "unsupported_avatar_format"),
    ],
)
async def test_rejects_empty_and_unsupported_files(client: AsyncClient, data: bytes, status: int, code: str) -> None:
    res = await client.put("/api/account/avatar", files={"file": ("a.png", data, "image/png")})

    assert res.status_code == status
    assert res.json()["code"] == code


async def test_rejects_a_file_over_the_limit(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "MAX_AVATAR_BYTES", 10)

    res = await client.put("/api/account/avatar", files={"file": ("a.png", _PNG, "image/png")})

    assert res.status_code == 413
    assert res.json()["code"] == "avatar_too_large"


async def test_delete_removes_only_the_current_users_avatar(client: AsyncClient) -> None:
    mine = await _upload(client, _PNG)
    Users.current = "avatar-user-b"
    theirs = await _upload(client, _PNG)

    res = await client.delete("/api/account/avatar")

    assert res.status_code == 204
    assert (await client.get(theirs)).status_code == 404
    assert (await client.get(mine)).status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/avatars/avatar-user-a/not-a-uuid.png",
        "/api/avatars/avatar-user-a/0123456789abcdef0123456789abcdef.gif",
        "/api/avatars/bad.user/0123456789abcdef0123456789abcdef.png",
        "/api/avatars/avatar-user-a/0123456789abcdef0123456789abcdef.png",
    ],
)
async def test_unknown_or_malformed_paths_are_not_found(client: AsyncClient, path: str) -> None:
    res = await client.get(path)

    assert res.status_code == 404
    assert res.json()["code"] == "avatar_not_found"


async def test_upload_requires_authentication(client: AsyncClient) -> None:
    app.dependency_overrides.pop(get_current_user)

    res = await client.put("/api/account/avatar", files={"file": ("a.png", _PNG, "image/png")})

    assert res.status_code in (401, 403)
