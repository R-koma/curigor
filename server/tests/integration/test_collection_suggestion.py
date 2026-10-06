import uuid
from collections.abc import AsyncGenerator

import asyncpg
import pytest
import pytest_asyncio

from core.config import EMBEDDING_DIMENSIONS
from repositories import note_collection_repository, note_embedding_repository, note_repository
from services import note_embedding
from services.collection_suggestion import suggest_collection_by_similarity
from services.note_embedding import refresh_note_embedding

pytestmark = pytest.mark.asyncio(loop_scope="session")

_MODEL = "test-embedding"


def _unit(*weights: float) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for i, w in enumerate(weights):
        vector[i] = w
    return vector


async def _note(
    conn: asyncpg.Connection, user_id: str, vector: list[float], *, collection: str | None = None
) -> uuid.UUID:
    note_id = uuid.uuid4()
    await note_repository.insert(conn, note_id=note_id, user_id=user_id, topic="T", content="c", summary="s")
    await note_embedding_repository.upsert(conn, note_id, user_id, vector, _MODEL, f"hash-{note_id}")
    if collection is not None:
        row = await note_collection_repository.get_or_create(conn, user_id, collection)
        await note_repository.set_collection(conn, note_id, user_id, row["id"])
    return note_id


async def _suggested(conn: asyncpg.Connection, note_id: uuid.UUID) -> str | None:
    value: str | None = await conn.fetchval("SELECT suggested_collection FROM notes WHERE id = $1", note_id)
    return value


async def test_votes_group_the_nearby_notes_by_collection(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0))
    await _note(db_conn, user_id, _unit(0.9, 0.1), collection="OS入門")
    await _note(db_conn, user_id, _unit(0.8, 0.2), collection="OS入門")
    await _note(db_conn, user_id, _unit(0.95, 0.05), collection="料理")
    await _note(db_conn, user_id, _unit(0.99, 0.01))
    await _note(db_conn, user_id, _unit(0.0, 1.0), collection="遠いまとめ")

    votes = await note_embedding_repository.find_collection_votes(
        db_conn, source, user_id, limit=10, min_similarity=0.5
    )

    assert [v["name"] for v in votes] == ["OS入門", "料理"]
    assert votes[0]["score"] > votes[1]["score"]
    assert votes[1]["best"] > votes[0]["best"] - 0.1


async def test_votes_ignore_notes_below_the_threshold(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0))
    await _note(db_conn, user_id, _unit(0.3, 0.7), collection="遠いまとめ")

    votes = await note_embedding_repository.find_collection_votes(
        db_conn, source, user_id, limit=10, min_similarity=0.5
    )

    assert votes == []


async def test_suggests_the_collection_of_the_nearest_notes(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0))
    await _note(db_conn, user_id, _unit(0.9, 0.1), collection="OS入門")

    assert await suggest_collection_by_similarity(db_conn, source, user_id) == "OS入門"
    assert await _suggested(db_conn, source) == "OS入門"


async def test_suggests_nothing_without_a_nearby_collection(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0))
    await _note(db_conn, user_id, _unit(0.95, 0.05))

    assert await suggest_collection_by_similarity(db_conn, source, user_id) is None
    assert await _suggested(db_conn, source) is None


async def test_keeps_a_suggestion_that_already_exists(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0))
    await _note(db_conn, user_id, _unit(0.9, 0.1), collection="OS入門")
    await db_conn.execute("UPDATE notes SET suggested_collection = '教科書' WHERE id = $1", source)

    assert await suggest_collection_by_similarity(db_conn, source, user_id) is None
    assert await _suggested(db_conn, source) == "教科書"


async def test_does_not_suggest_to_a_note_that_is_already_in_a_collection(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0), collection="料理")
    await _note(db_conn, user_id, _unit(0.9, 0.1), collection="OS入門")

    assert await suggest_collection_by_similarity(db_conn, source, user_id) is None


async def test_does_not_bring_back_a_dismissed_suggestion(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0))
    await _note(db_conn, user_id, _unit(0.9, 0.1), collection="OS入門")
    await suggest_collection_by_similarity(db_conn, source, user_id)

    await note_repository.clear_suggested_collection(db_conn, source, user_id)

    assert await suggest_collection_by_similarity(db_conn, source, user_id) is None
    assert await _suggested(db_conn, source) is None


async def test_does_not_suggest_again_after_the_user_removes_the_note_from_a_collection(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0), collection="OS入門")
    await _note(db_conn, user_id, _unit(0.9, 0.1), collection="OS入門")

    await note_repository.set_collection(db_conn, source, user_id, None)

    assert await suggest_collection_by_similarity(db_conn, source, user_id) is None


async def test_putting_a_note_in_a_collection_is_not_a_dismissal(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0), collection="OS入門")

    dismissed = await db_conn.fetchval("SELECT collection_suggestion_dismissed_at FROM notes WHERE id = $1", source)

    assert dismissed is None


async def test_lists_the_embedded_notes_that_still_need_a_suggestion(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    open_note = await _note(db_conn, user_id, _unit(1.0))
    await _note(db_conn, user_id, _unit(0.9, 0.1), collection="OS入門")
    suggested = await _note(db_conn, user_id, _unit(0.8, 0.2))
    await db_conn.execute("UPDATE notes SET suggested_collection = '教科書' WHERE id = $1", suggested)
    dismissed = await _note(db_conn, user_id, _unit(0.7, 0.3))
    await note_repository.clear_suggested_collection(db_conn, dismissed, user_id)

    targets = await note_embedding_repository.find_unsuggested_note_ids(db_conn, _MODEL)

    assert targets == [(open_note, user_id)]


class _FakeEmbedder:
    model = _MODEL

    async def embed(self, text: str) -> list[float]:
        return _unit(1.0)


@pytest_asyncio.fixture(loop_scope="session")
async def _use_test_pool(test_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None]:
    async def fake_get_pool() -> asyncpg.Pool:
        return test_pool

    monkeypatch.setattr(note_embedding, "get_pool", fake_get_pool)
    yield


@pytest.mark.usefixtures("_use_test_pool")
async def test_refreshing_an_embedding_suggests_a_collection(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    await _note(db_conn, user_id, _unit(0.95, 0.05), collection="OS入門")
    note_id = uuid.uuid4()
    await note_repository.insert(db_conn, note_id=note_id, user_id=user_id, topic="T", content="c", summary="s")

    assert await refresh_note_embedding(note_id, user_id, _FakeEmbedder()) is True

    assert await _suggested(db_conn, note_id) == "OS入門"
