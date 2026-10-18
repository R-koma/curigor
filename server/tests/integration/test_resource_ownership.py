import io
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.dependencies import get_app_checkpointer, get_current_user
from api.routes import dialogue_session as dialogue_session_routes
from core import database
from core.database import DBConnection
from core.terms import TERMS_VERSION
from graph.version import GRAPH_VERSION
from main import app
from repositories import (
    collection_synthesis_repository,
    dialogue_message_image_repository,
    dialogue_message_repository,
    dialogue_session_repository,
    feedback_repository,
    hint_dismissal_repository,
    note_collection_repository,
    note_link_repository,
    note_repository,
    note_revision_repository,
    review_schedule_repository,
    study_memo_repository,
    user_consent_repository,
)
from speech import get_synthesizer
from storage import get_storage
from storage.local import LocalObjectStorage
from transcription import get_transcriber

pytestmark = pytest.mark.asyncio(loop_scope="session")

USER_A = "ownership-user-a"
USER_B = "ownership-user-b"


@dataclass
class Owned:
    note_id: UUID
    other_note_id: UUID
    collection_id: UUID
    link_id: UUID
    schedule_id: UUID
    upcoming_schedule_id: UUID
    session_id: UUID
    image_id: UUID
    active_session_id: UUID
    memo_id: UUID

    def ids(self) -> set[str]:
        return {str(v) for v in vars(self).values()}


@dataclass
class FakeTranscriber:
    model: str = "fake-transcriber"
    calls: list[bytes] = field(default_factory=list)

    async def transcribe(self, data: bytes, mime_type: str, prompt: str | None, keywords: list[str] | None) -> str:
        self.calls.append(data)
        return "text"


@dataclass
class FakeSynthesizer:
    model: str = "fake-synthesizer"
    calls: list[str] = field(default_factory=list)

    async def stream(self, text: str, speed: float) -> AsyncIterator[bytes]:
        self.calls.append(text)
        yield b"\x00\x00"


@dataclass
class FakeCheckpointer:
    deleted_threads: list[str] = field(default_factory=list)

    async def adelete_thread(self, thread_id: str) -> None:
        self.deleted_threads.append(thread_id)


@dataclass
class Env:
    client: AsyncClient
    a: Owned
    b: Owned
    transcriber: FakeTranscriber
    synthesizer: FakeSynthesizer
    checkpointer: FakeCheckpointer


async def _create_user(conn: DBConnection, user_id: str) -> None:
    await conn.execute(
        'INSERT INTO "user" (id, name, email, "emailVerified") VALUES ($1, $2, $3, true) ON CONFLICT (id) DO NOTHING',
        user_id,
        user_id,
        f"{user_id}@example.com",
    )
    await user_consent_repository.record(conn, user_id, TERMS_VERSION)


async def _seed(conn: DBConnection, user_id: str, storage: LocalObjectStorage) -> Owned:
    now = datetime.now(UTC)
    collection = await note_collection_repository.get_or_create(conn, user_id, "まとめ")

    note_id = uuid4()
    await note_repository.insert(
        conn, note_id=note_id, user_id=user_id, topic="二分探索", content="c", summary="s", suggested_collection="候補"
    )
    await note_repository.set_collection(conn, note_id, user_id, collection["id"])
    other_note_id = uuid4()
    await note_repository.insert(
        conn, note_id=other_note_id, user_id=user_id, topic="ハッシュ", content="c", summary="s"
    )
    await note_link_repository.upsert_suggestions(
        conn, note_id, user_id, [{"note_id": other_note_id, "similarity": 0.9}]
    )
    link_id = await conn.fetchval("SELECT id FROM note_links WHERE user_id = $1", user_id)

    schedule = await review_schedule_repository.insert(conn, note_id, now - timedelta(days=1))
    upcoming = await review_schedule_repository.insert(conn, other_note_id, now + timedelta(days=3))

    session_id = uuid4()
    await dialogue_session_repository.create(
        conn, session_id=session_id, user_id=user_id, session_type="learning", graph_version=GRAPH_VERSION
    )
    await dialogue_session_repository.update_note_id(conn, session_id, note_id)
    await dialogue_session_repository.update_status(conn, session_id, "completed")
    message = await dialogue_message_repository.insert(conn, session_id, "user", "見て", 1)
    assert message is not None
    storage_key = f"dialogue_images/{session_id}/0.png"
    await storage.put(storage_key, b"png-bytes", "image/png")
    await dialogue_message_image_repository.insert_many(conn, message["id"], [(storage_key, "image/png")])
    image_id = await conn.fetchval(
        "SELECT id FROM dialogue_message_images WHERE dialogue_message_id = $1", message["id"]
    )
    await feedback_repository.insert(conn, note_id, session_id, "high", "強み", "改善点")
    await note_revision_repository.insert(conn, note_id, session_id, "前の本文")

    await collection_synthesis_repository.upsert(
        conn,
        collection_id=collection["id"],
        content="まとめ",
        connections=[],
        contradictions=[],
        gaps=[],
        source_notes=[],
    )

    explore_session_id = uuid4()
    await dialogue_session_repository.create(
        conn, session_id=explore_session_id, user_id=user_id, session_type="explore", graph_version=GRAPH_VERSION
    )
    await dialogue_session_repository.update_status(conn, explore_session_id, "completed")
    memo_id = await study_memo_repository.insert(
        conn,
        user_id=user_id,
        dialogue_session_id=explore_session_id,
        topic="二分探索",
        source="",
        summary="",
        overview=[],
        glossary=[],
        questions=[],
        depth_map={"aspects": []},
    )

    active_session_id = uuid4()
    await dialogue_session_repository.create(
        conn, session_id=active_session_id, user_id=user_id, session_type="learning", graph_version=GRAPH_VERSION
    )

    await hint_dismissal_repository.dismiss(conn, user_id, "dashboard")

    return Owned(
        note_id=note_id,
        other_note_id=other_note_id,
        collection_id=collection["id"],
        link_id=link_id,
        schedule_id=schedule["id"],
        upcoming_schedule_id=upcoming["id"],
        session_id=session_id,
        image_id=image_id,
        active_session_id=active_session_id,
        memo_id=memo_id,
    )


_SNAPSHOT_QUERIES = {
    "notes": "SELECT * FROM notes WHERE user_id = $1 ORDER BY id",
    "note_collections": "SELECT * FROM note_collections WHERE user_id = $1 ORDER BY id",
    "note_links": "SELECT * FROM note_links WHERE user_id = $1 ORDER BY id",
    "review_schedules": (
        "SELECT rs.* FROM review_schedules rs JOIN notes n ON n.id = rs.note_id WHERE n.user_id = $1 ORDER BY rs.id"
    ),
    "dialogue_sessions": "SELECT * FROM dialogue_sessions WHERE user_id = $1 ORDER BY id",
    "collection_syntheses": (
        "SELECT s.* FROM collection_syntheses s JOIN note_collections c ON c.id = s.collection_id "
        "WHERE c.user_id = $1 ORDER BY s.collection_id"
    ),
    "user_hint_dismissals": "SELECT * FROM user_hint_dismissals WHERE user_id = $1 ORDER BY hint_id",
    "study_memos": "SELECT * FROM study_memos WHERE user_id = $1 ORDER BY id",
}


async def _snapshot(pool: asyncpg.Pool, user_id: str) -> dict[str, list[dict[str, Any]]]:
    async with pool.acquire() as conn:
        return {table: [dict(r) for r in await conn.fetch(q, user_id)] for table, q in _SNAPSHOT_QUERIES.items()}


@pytest_asyncio.fixture(loop_scope="session")
async def env(test_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> AsyncGenerator[Env]:
    storage = LocalObjectStorage(tmp_path)
    async with test_pool.acquire() as conn:
        await _create_user(conn, USER_A)
        await _create_user(conn, USER_B)
        a = await _seed(conn, USER_A, storage)
        b = await _seed(conn, USER_B, storage)

    monkeypatch.setattr(database, "_pool", test_pool)
    monkeypatch.setattr(dialogue_session_routes, "get_storage", lambda: storage)
    transcriber = FakeTranscriber()
    synthesizer = FakeSynthesizer()
    checkpointer = FakeCheckpointer()
    app.dependency_overrides[get_current_user] = lambda: USER_A
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_app_checkpointer] = lambda: checkpointer
    app.dependency_overrides[get_transcriber] = lambda: transcriber
    app.dependency_overrides[get_synthesizer] = lambda: synthesizer
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield Env(
                client=client, a=a, b=b, transcriber=transcriber, synthesizer=synthesizer, checkpointer=checkpointer
            )
    finally:
        for dependency in (get_current_user, get_transcriber, get_synthesizer, get_storage, get_app_checkpointer):
            app.dependency_overrides.pop(dependency, None)


def _body(template: dict[str, Any], owner: Owned) -> dict[str, Any]:
    return {k: v.format(r=owner) if isinstance(v, str) else v for k, v in template.items()}


RESOURCE_CALLS = [
    ("GET", "/api/notes/{r.note_id}", None, 200),
    ("PATCH", "/api/notes/{r.note_id}", {"category": "アルゴリズム"}, 200),
    ("DELETE", "/api/notes/{r.note_id}", None, 204),
    ("PUT", "/api/notes/{r.note_id}/collection", {"collection_id": None}, 204),
    ("DELETE", "/api/notes/{r.note_id}/collection-suggestion", None, 204),
    ("GET", "/api/notes/{r.note_id}/links", None, 200),
    ("PUT", "/api/notes/{r.note_id}/links/{r.link_id}", {"status": "accepted"}, 204),
    ("GET", "/api/notes/{r.note_id}/feedbacks", None, 200),
    ("GET", "/api/notes/{r.note_id}/revisions", None, 200),
    ("GET", "/api/collections/{r.collection_id}", None, 200),
    ("PATCH", "/api/collections/{r.collection_id}", {"name": "新しい名前"}, 200),
    ("DELETE", "/api/collections/{r.collection_id}", None, 204),
    ("GET", "/api/collections/{r.collection_id}/synthesis", None, 200),
    ("DELETE", "/api/dialogue-sessions/{r.session_id}", None, 204),
    ("GET", "/api/dialogue-sessions/{r.session_id}/messages", None, 200),
    ("GET", "/api/dialogue-sessions/{r.session_id}/images/{r.image_id}", None, 200),
    ("GET", "/api/dialogue-sessions/{r.session_id}/note-status", None, 200),
    ("PATCH", "/api/review-schedules/{r.schedule_id}", {}, 200),
    ("GET", "/api/study-memos/{r.memo_id}", None, 200),
    ("PATCH", "/api/study-memos/{r.memo_id}", {"summary": "書き直した要約"}, 200),
    ("DELETE", "/api/study-memos/{r.memo_id}", None, 204),
]


def _call_id(call: tuple[str, str, Any, int]) -> str:
    return f"{call[0]} {call[1]}"


async def _request(env: Env, method: str, path: str, body: dict[str, Any] | None, owner: Owned) -> Any:
    return await env.client.request(method, path.format(r=owner), json=None if body is None else _body(body, owner))


@pytest.mark.parametrize("call", RESOURCE_CALLS, ids=_call_id)
async def test_own_resource_succeeds(env: Env, call: tuple[str, str, Any, int]) -> None:
    method, path, body, expected = call

    response = await _request(env, method, path, body, env.a)

    assert response.status_code == expected, response.text


@pytest.mark.parametrize("call", RESOURCE_CALLS, ids=_call_id)
async def test_other_users_resource_is_not_found_and_left_unchanged(
    env: Env, test_pool: asyncpg.Pool, call: tuple[str, str, Any, int]
) -> None:
    method, path, body, _ = call
    before = await _snapshot(test_pool, USER_B)

    response = await _request(env, method, path, body, env.b)

    assert response.status_code == 404, response.text
    assert await _snapshot(test_pool, USER_B) == before
    assert str(env.b.session_id) not in env.checkpointer.deleted_threads


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/notes/{a.note_id}/links/{b.link_id}", {"status": "accepted"}),
        ("/api/notes/{b.note_id}/links/{a.link_id}", {"status": "accepted"}),
    ],
)
async def test_a_link_is_not_found_through_another_users_note(
    env: Env, test_pool: asyncpg.Pool, path: str, body: dict[str, Any]
) -> None:
    before = await _snapshot(test_pool, USER_B)

    response = await env.client.put(path.format(a=env.a, b=env.b), json=body)

    assert response.status_code == 404
    assert await _snapshot(test_pool, USER_B) == before


async def test_an_image_of_another_users_session_is_not_found_through_an_own_session(env: Env) -> None:
    response = await env.client.get(f"/api/dialogue-sessions/{env.a.session_id}/images/{env.b.image_id}")

    assert response.status_code == 404


async def test_an_own_note_cannot_join_another_users_collection(env: Env, test_pool: asyncpg.Pool) -> None:
    before_a = await _snapshot(test_pool, USER_A)
    before_b = await _snapshot(test_pool, USER_B)

    response = await env.client.put(
        f"/api/notes/{env.a.note_id}/collection", json={"collection_id": str(env.b.collection_id)}
    )

    assert response.status_code == 404
    assert await _snapshot(test_pool, USER_A) == before_a
    assert await _snapshot(test_pool, USER_B) == before_b


async def test_synthesis_of_another_users_collection_is_not_found_before_generation(env: Env) -> None:
    response = await env.client.post(f"/api/collections/{env.b.collection_id}/synthesis")

    assert response.status_code == 404


async def test_speech_for_another_users_session_is_not_found_before_synthesis(env: Env) -> None:
    response = await env.client.post(
        "/api/speech", json={"text": "こんにちは", "dialogue_session_id": str(env.b.session_id)}
    )

    assert response.status_code == 404
    assert env.synthesizer.calls == []


async def test_transcription_for_another_users_session_is_not_found_before_transcription(env: Env) -> None:
    response = await env.client.post(
        "/api/transcriptions",
        data={"dialogue_session_id": str(env.b.session_id)},
        files={"audio": ("a.wav", io.BytesIO(b"RIFF"), "audio/wav")},
    )

    assert response.status_code == 404
    assert env.transcriber.calls == []


async def _listed_ids(env: Env) -> set[str]:
    listed: set[str] = set()
    for path in (
        "/api/notes",
        "/api/collections",
        "/api/study-memos",
        "/api/review-schedules",
        "/api/review-schedules/upcoming",
        "/api/dialogue-sessions/active",
    ):
        response = await env.client.get(path)
        assert response.status_code == 200, path
        listed |= _uuids_in(response.json())
    return listed


def _uuids_in(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(_uuids_in(v) for v in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(_uuids_in(v) for v in value)) if value else set()
    if isinstance(value, str):
        try:
            return {str(UUID(value))}
        except ValueError:
            return set()
    return set()


async def test_lists_hold_only_own_resources(env: Env) -> None:
    listed = await _listed_ids(env)

    assert {
        str(env.a.note_id),
        str(env.a.other_note_id),
        str(env.a.collection_id),
        str(env.a.memo_id),
        str(env.a.schedule_id),
        str(env.a.upcoming_schedule_id),
        str(env.a.active_session_id),
    } <= listed
    assert not listed & env.b.ids()


async def test_hint_dismissals_are_per_user(env: Env, test_pool: asyncpg.Pool) -> None:
    async with test_pool.acquire() as conn:
        await hint_dismissal_repository.dismiss(conn, USER_B, "learn_start")
    before_b = await _snapshot(test_pool, USER_B)

    listed = await env.client.get("/api/hints/dismissals")
    reset = await env.client.delete("/api/hints/dismissals")

    assert listed.json() == {"dismissed": ["dashboard"]}
    assert reset.status_code == 204
    assert await _snapshot(test_pool, USER_B) == before_b
