import uuid
from collections.abc import AsyncGenerator

import asyncpg
import pytest
import pytest_asyncio

from core.config import EMBEDDING_DIMENSIONS
from embedding import EmbeddingError
from repositories import note_embedding_repository, note_repository
from services import note_embedding
from services.note_embedding import refresh_note_embedding

pytestmark = pytest.mark.asyncio(loop_scope="session")


class FakeEmbedder:
    model = "fake-embedding"

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[str] = []
        self._fail = fail

    async def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        if self._fail:
            raise EmbeddingError("boom")
        return [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)


@pytest_asyncio.fixture(loop_scope="session", autouse=True)
async def _use_test_pool(test_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None]:
    async def fake_get_pool() -> asyncpg.Pool:
        return test_pool

    monkeypatch.setattr(note_embedding, "get_pool", fake_get_pool)
    yield


async def _insert_note(conn: asyncpg.Connection, user_id: str, content: str = "本文") -> uuid.UUID:
    note_id = uuid.uuid4()
    await note_repository.insert(
        conn, note_id=note_id, user_id=user_id, topic="ページング", content=content, summary="要約"
    )
    return note_id


async def test_creates_an_embedding_from_the_note(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    note_id = await _insert_note(db_conn, test_user["id"])
    embedder = FakeEmbedder()

    assert await refresh_note_embedding(note_id, test_user["id"], embedder) is True

    assert embedder.calls == ["ページング\n\n要約\n\n本文"]
    assert await note_embedding_repository.find_content_hash(db_conn, note_id, embedder.model) is not None


async def test_skips_the_api_when_the_note_is_unchanged(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    note_id = await _insert_note(db_conn, test_user["id"])
    embedder = FakeEmbedder()
    await refresh_note_embedding(note_id, test_user["id"], embedder)

    assert await refresh_note_embedding(note_id, test_user["id"], embedder) is False
    assert len(embedder.calls) == 1


async def test_recreates_the_embedding_after_an_edit(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    note_id = await _insert_note(db_conn, test_user["id"])
    embedder = FakeEmbedder()
    await refresh_note_embedding(note_id, test_user["id"], embedder)
    await note_repository.update(db_conn, note_id=note_id, user_id=test_user["id"], content="書き直した本文")

    assert await refresh_note_embedding(note_id, test_user["id"], embedder) is True
    assert embedder.calls[-1].endswith("書き直した本文")


async def test_api_failure_leaves_no_embedding(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    note_id = await _insert_note(db_conn, test_user["id"])
    embedder = FakeEmbedder(fail=True)

    assert await refresh_note_embedding(note_id, test_user["id"], embedder) is False
    assert await note_embedding_repository.find_content_hash(db_conn, note_id, embedder.model) is None


async def test_missing_note_is_ignored(test_user: dict[str, str]) -> None:
    embedder = FakeEmbedder()

    assert await refresh_note_embedding(uuid.uuid4(), test_user["id"], embedder) is False
    assert embedder.calls == []
