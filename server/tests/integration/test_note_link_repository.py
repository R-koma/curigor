import uuid

import asyncpg
import pytest

from core import config
from core.config import EMBEDDING_DIMENSIONS
from repositories import note_collection_repository, note_embedding_repository, note_link_repository, note_repository
from services.note_links import suggest_note_links

pytestmark = pytest.mark.asyncio(loop_scope="session")

_MODEL = "test-embedding"


def _unit(*weights: float) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for i, w in enumerate(weights):
        vector[i] = w
    return vector


async def _note(conn: asyncpg.Connection, user_id: str, vector: list[float], topic: str = "T") -> uuid.UUID:
    note_id = uuid.uuid4()
    await note_repository.insert(conn, note_id=note_id, user_id=user_id, topic=topic, content="c", summary="s")
    await note_embedding_repository.upsert(conn, note_id, user_id, vector, _MODEL, f"hash-{note_id}")
    return note_id


async def _collect(conn: asyncpg.Connection, user_id: str, name: str, *note_ids: uuid.UUID) -> uuid.UUID:
    collection = await note_collection_repository.get_or_create(conn, user_id, name)
    for note_id in note_ids:
        await note_repository.set_collection(conn, note_id, user_id, collection["id"])
    collection_id: uuid.UUID = collection["id"]
    return collection_id


async def test_candidates_exclude_notes_in_the_same_collection(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0))
    sibling = await _note(db_conn, user_id, _unit(0.95, 0.05))
    elsewhere = await _note(db_conn, user_id, _unit(0.9, 0.1))
    loose = await _note(db_conn, user_id, _unit(0.85, 0.15))
    await _collect(db_conn, user_id, f"same-{source}", source, sibling)
    await _collect(db_conn, user_id, f"other-{source}", elsewhere)

    candidates = await note_link_repository.find_link_candidates(
        db_conn, source, user_id, limit=10, min_similarity=0.5
    )

    ids = [c["note_id"] for c in candidates]
    assert sibling not in ids
    assert ids[:2] == [elsewhere, loose]


async def test_a_note_without_a_collection_compares_with_every_note(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0))
    collected = await _note(db_conn, user_id, _unit(0.9, 0.1))
    await _collect(db_conn, user_id, f"c-{source}", collected)

    candidates = await note_link_repository.find_link_candidates(
        db_conn, source, user_id, limit=10, min_similarity=0.5
    )

    assert collected in [c["note_id"] for c in candidates]


async def test_upsert_keeps_a_dismissed_link_dismissed(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0))
    other = await _note(db_conn, user_id, _unit(0.9, 0.1))
    await note_link_repository.upsert_suggestions(db_conn, source, user_id, [{"note_id": other, "similarity": 0.9}])
    [link] = await note_link_repository.find_by_note_id(db_conn, source, user_id)
    await note_link_repository.set_status(db_conn, link["id"], source, user_id, "dismissed")

    await note_link_repository.upsert_suggestions(db_conn, other, user_id, [{"note_id": source, "similarity": 0.95}])

    assert await note_link_repository.find_by_note_id(db_conn, source, user_id) == []
    status = await db_conn.fetchval("SELECT status FROM note_links WHERE id = $1", link["id"])
    assert status == "dismissed"


async def test_a_link_is_seen_from_both_notes(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0), topic="ロードバランサー")
    other = await _note(db_conn, user_id, _unit(0.9, 0.1), topic="スケーリング")
    await _collect(db_conn, user_id, f"sd-{source}", other)
    await note_link_repository.upsert_suggestions(db_conn, source, user_id, [{"note_id": other, "similarity": 0.9}])

    [from_source] = await note_link_repository.find_by_note_id(db_conn, source, user_id)
    [from_other] = await note_link_repository.find_by_note_id(db_conn, other, user_id)

    assert from_source["note_id"] == other
    assert from_source["topic"] == "スケーリング"
    assert from_source["collection_name"] == f"sd-{source}"
    assert from_other["note_id"] == source
    assert from_source["id"] == from_other["id"]


async def test_accepted_links_come_first(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0))
    closer = await _note(db_conn, user_id, _unit(0.95, 0.05))
    farther = await _note(db_conn, user_id, _unit(0.8, 0.2))
    await note_link_repository.upsert_suggestions(
        db_conn,
        source,
        user_id,
        [{"note_id": closer, "similarity": 0.95}, {"note_id": farther, "similarity": 0.8}],
    )
    links = await note_link_repository.find_by_note_id(db_conn, source, user_id)
    farther_link = next(link for link in links if link["note_id"] == farther)
    await note_link_repository.set_status(db_conn, farther_link["id"], source, user_id, "accepted")

    ordered = await note_link_repository.find_by_note_id(db_conn, source, user_id)

    assert [(link["note_id"], link["status"]) for link in ordered] == [(farther, "accepted"), (closer, "suggested")]


async def test_a_suggestion_is_hidden_once_both_notes_share_a_collection(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0))
    other = await _note(db_conn, user_id, _unit(0.9, 0.1))
    await note_link_repository.upsert_suggestions(db_conn, source, user_id, [{"note_id": other, "similarity": 0.9}])

    await _collect(db_conn, user_id, f"later-{source}", source, other)

    assert await note_link_repository.find_by_note_id(db_conn, source, user_id) == []


async def test_set_status_only_touches_a_link_of_that_note(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0))
    other = await _note(db_conn, user_id, _unit(0.9, 0.1))
    unrelated = await _note(db_conn, user_id, _unit(0.0, 1.0))
    await note_link_repository.upsert_suggestions(db_conn, source, user_id, [{"note_id": other, "similarity": 0.9}])
    [link] = await note_link_repository.find_by_note_id(db_conn, source, user_id)

    assert await note_link_repository.set_status(db_conn, link["id"], unrelated, user_id, "accepted") is False
    assert await note_link_repository.set_status(db_conn, link["id"], source, "someone-else", "accepted") is False
    assert await note_link_repository.set_status(db_conn, link["id"], other, user_id, "accepted") is True


async def test_suggest_note_links_drops_a_suggestion_that_fell_below_the_threshold(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    source = await _note(db_conn, user_id, _unit(1.0))
    other = await _note(db_conn, user_id, _unit(0.95, 0.05))
    assert await suggest_note_links(db_conn, source, user_id) >= 1
    assert other in [link["note_id"] for link in await note_link_repository.find_by_note_id(db_conn, source, user_id)]

    await note_embedding_repository.upsert(db_conn, other, user_id, _unit(0.0, 1.0), _MODEL, "rewritten")
    await suggest_note_links(db_conn, other, user_id)

    remaining = [link["note_id"] for link in await note_link_repository.find_by_note_id(db_conn, source, user_id)]
    assert other not in remaining
    assert config.NOTE_LINK_MIN_SIMILARITY > 0
