import uuid

import asyncpg
import pytest

from core.config import EMBEDDING_DIMENSIONS
from repositories import note_embedding_repository, note_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")

_MODEL = "test-embedding"


def _unit(*weights: float) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for i, w in enumerate(weights):
        vector[i] = w
    return vector


async def _note_with_embedding(conn: asyncpg.Connection, user_id: str, vector: list[float]) -> uuid.UUID:
    note_id = uuid.uuid4()
    await note_repository.insert(conn, note_id=note_id, user_id=user_id, topic="T", content="c", summary="s")
    await note_embedding_repository.upsert(conn, note_id, user_id, vector, _MODEL, f"hash-{note_id}")
    return note_id


async def test_upsert_replaces_the_embedding_and_hash(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    note_id = await _note_with_embedding(db_conn, test_user["id"], _unit(1.0))

    await note_embedding_repository.upsert(db_conn, note_id, test_user["id"], _unit(0.0, 1.0), _MODEL, "new-hash")

    assert await note_embedding_repository.find_content_hash(db_conn, note_id, _MODEL) == "new-hash"


async def test_find_content_hash_is_none_for_another_model(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    note_id = await _note_with_embedding(db_conn, test_user["id"], _unit(1.0))

    assert await note_embedding_repository.find_content_hash(db_conn, note_id, "other-model") is None


async def test_upsert_ignores_a_note_of_another_user(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    note_id = uuid.uuid4()
    await note_repository.insert(
        db_conn, note_id=note_id, user_id=test_user["id"], topic="T", content="c", summary="s"
    )

    await note_embedding_repository.upsert(db_conn, note_id, "someone-else", _unit(1.0), _MODEL, "h")

    assert await note_embedding_repository.find_content_hash(db_conn, note_id, _MODEL) is None


async def test_find_similar_notes_orders_by_similarity_and_applies_the_threshold(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    source = await _note_with_embedding(db_conn, user_id, _unit(1.0))
    closest = await _note_with_embedding(db_conn, user_id, _unit(0.9, 0.1))
    close = await _note_with_embedding(db_conn, user_id, _unit(0.6, 0.4))
    await _note_with_embedding(db_conn, user_id, _unit(0.0, 1.0))

    similar = await note_embedding_repository.find_similar_notes(
        db_conn, source, user_id, limit=10, min_similarity=0.5
    )

    assert [r["note_id"] for r in similar] == [closest, close]
    assert similar[0]["similarity"] > similar[1]["similarity"]


async def test_find_similar_notes_does_not_cross_users(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    other_user = "embedding-other-user"
    await db_conn.execute(
        """INSERT INTO "user" (id, name, email, "emailVerified") VALUES ($1, 'o', 'o@example.com', true)
        ON CONFLICT (id) DO NOTHING""",
        other_user,
    )
    source = await _note_with_embedding(db_conn, test_user["id"], _unit(1.0))
    await _note_with_embedding(db_conn, other_user, _unit(1.0))

    similar = await note_embedding_repository.find_similar_notes(
        db_conn, source, test_user["id"], limit=10, min_similarity=0.0
    )

    assert similar == []


async def test_find_note_ids_without_embedding(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    embedded = await _note_with_embedding(db_conn, test_user["id"], _unit(1.0))
    missing = uuid.uuid4()
    await note_repository.insert(
        db_conn, note_id=missing, user_id=test_user["id"], topic="T", content="c", summary="s"
    )

    targets = await note_embedding_repository.find_note_ids_without_embedding(db_conn, _MODEL)

    assert (missing, test_user["id"]) in targets
    assert all(note_id != embedded for note_id, _ in targets)


async def test_find_notes_near_embedding_returns_topic_and_summary_by_similarity(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    closest = await _note_with_embedding(db_conn, user_id, _unit(0.9, 0.1))
    close = await _note_with_embedding(db_conn, user_id, _unit(0.6, 0.4))
    await _note_with_embedding(db_conn, user_id, _unit(0.0, 1.0))

    near = await note_embedding_repository.find_notes_near_embedding(
        db_conn, user_id, _unit(1.0), _MODEL, limit=10, min_similarity=0.5
    )

    assert [r["note_id"] for r in near] == [closest, close]
    assert near[0]["topic"] == "T"
    assert near[0]["summary"] == "s"


async def test_find_notes_near_embedding_applies_the_limit(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    closest = await _note_with_embedding(db_conn, user_id, _unit(0.9, 0.1))
    await _note_with_embedding(db_conn, user_id, _unit(0.6, 0.4))

    near = await note_embedding_repository.find_notes_near_embedding(
        db_conn, user_id, _unit(1.0), _MODEL, limit=1, min_similarity=0.0
    )

    assert [r["note_id"] for r in near] == [closest]


async def test_find_notes_near_embedding_ignores_other_users_and_models(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    other_user = "embedding-other-user"
    await db_conn.execute(
        """INSERT INTO "user" (id, name, email, "emailVerified") VALUES ($1, 'o', 'o@example.com', true)
        ON CONFLICT (id) DO NOTHING""",
        other_user,
    )
    await _note_with_embedding(db_conn, other_user, _unit(1.0))
    note_id = uuid.uuid4()
    await note_repository.insert(
        db_conn, note_id=note_id, user_id=test_user["id"], topic="T", content="c", summary="s"
    )
    await note_embedding_repository.upsert(db_conn, note_id, test_user["id"], _unit(1.0), "other-model", "h")

    near = await note_embedding_repository.find_notes_near_embedding(
        db_conn, test_user["id"], _unit(1.0), _MODEL, limit=10, min_similarity=0.0
    )

    assert near == []
