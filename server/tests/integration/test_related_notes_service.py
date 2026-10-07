import uuid
from collections.abc import AsyncGenerator

import asyncpg
import pytest
import pytest_asyncio

from core.config import EMBEDDING_DIMENSIONS, MAX_RELATED_NOTE_SUMMARY_CHARS
from embedding import EmbeddingError
from repositories import note_embedding_repository, note_repository
from services import related_notes
from services.related_notes import build_query_text, find_related_notes

pytestmark = pytest.mark.asyncio(loop_scope="session")

_MODEL = "fake-embedding"


def _unit(*weights: float) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for i, w in enumerate(weights):
        vector[i] = w
    return vector


class FakeEmbedder:
    model = _MODEL

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[str] = []
        self._fail = fail

    async def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        if self._fail:
            raise EmbeddingError("boom")
        return _unit(1.0)


@pytest_asyncio.fixture(loop_scope="session", autouse=True)
async def _use_test_pool(test_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None]:
    async def fake_get_pool() -> asyncpg.Pool:
        return test_pool

    monkeypatch.setattr(related_notes, "get_pool", fake_get_pool)
    yield


async def _note(conn: asyncpg.Connection, user_id: str, topic: str, summary: str, vector: list[float]) -> str:
    note_id = uuid.uuid4()
    await note_repository.insert(conn, note_id=note_id, user_id=user_id, topic=topic, content="本文", summary=summary)
    await note_embedding_repository.upsert(conn, note_id, user_id, vector, _MODEL, f"hash-{note_id}")
    return str(note_id)


async def test_returns_close_notes_with_topic_and_summary(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    process = await _note(db_conn, user_id, "プロセス", "実行中のプログラムの単位", _unit(0.9, 0.1))
    await _note(db_conn, user_id, "料理", "無関係", _unit(0.0, 1.0))
    embedder = FakeEmbedder()

    notes = await find_related_notes(user_id=user_id, topic="システムコール", purpose="面接対策", embedder=embedder)

    assert notes == [{"note_id": process, "topic": "プロセス", "summary": "実行中のプログラムの単位"}]
    assert embedder.calls == ["システムコール\n\n面接対策"]


async def test_a_long_summary_is_truncated(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    await _note(db_conn, test_user["id"], "プロセス", "あ" * (MAX_RELATED_NOTE_SUMMARY_CHARS + 10), _unit(1.0))

    notes = await find_related_notes(user_id=test_user["id"], topic="T", purpose="", embedder=FakeEmbedder())

    assert notes[0]["summary"] == "あ" * MAX_RELATED_NOTE_SUMMARY_CHARS


async def test_embedding_failure_returns_no_notes(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    await _note(db_conn, test_user["id"], "プロセス", "s", _unit(1.0))

    assert (
        await find_related_notes(user_id=test_user["id"], topic="T", purpose="", embedder=FakeEmbedder(fail=True))
        == []
    )


async def test_blank_query_does_not_call_the_api(test_user: dict[str, str]) -> None:
    embedder = FakeEmbedder()

    assert await find_related_notes(user_id=test_user["id"], topic=" ", purpose="", embedder=embedder) == []
    assert embedder.calls == []


async def test_query_text_skips_a_blank_purpose() -> None:
    assert build_query_text(topic="システムコール", purpose="  ") == "システムコール"
