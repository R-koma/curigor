import uuid
from collections.abc import AsyncGenerator
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from repositories import dialogue_session_repository
from services import transcription_keywords
from services.transcription_keywords import KeywordSource, refresh_transcription_keywords

pytestmark = pytest.mark.asyncio(loop_scope="session")

_SOURCE = KeywordSource("TCP/IPの仕組み", ("3ウェイハンドシェイク", "再送制御"), "ネットワークの障害を調べたい")


class _FakeGenerator:
    def __init__(self, terms: list[str] | None = None, *, fail: bool = False) -> None:
        self.terms = terms if terms is not None else ["輻輳制御", "SYN", "TCP"]
        self.fail = fail
        self.sources: list[KeywordSource] = []

    async def __call__(self, source: KeywordSource, run_config: dict[str, Any] | None = None) -> list[str]:
        self.sources.append(source)
        if self.fail:
            raise RuntimeError("boom")
        return self.terms


@pytest_asyncio.fixture(loop_scope="session", autouse=True)
async def _use_test_pool(test_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None]:
    async def fake_get_pool() -> asyncpg.Pool:
        return test_pool

    monkeypatch.setattr(transcription_keywords, "get_pool", fake_get_pool)
    yield


async def _session(conn: asyncpg.Connection, user_id: str) -> uuid.UUID:
    session_id = uuid.uuid4()
    await dialogue_session_repository.create(
        conn=conn, session_id=session_id, user_id=user_id, session_type="learning", graph_version=1
    )
    return session_id


async def test_stores_the_topic_aspects_and_generated_terms(
    db_conn: asyncpg.Connection, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = await _session(db_conn, test_user["id"])
    generator = _FakeGenerator()
    monkeypatch.setattr(transcription_keywords, "generate_terms", generator)

    assert await refresh_transcription_keywords(session_id, test_user["id"], _SOURCE) is True

    keywords, source = await dialogue_session_repository.find_transcription_keywords(
        db_conn, session_id, test_user["id"]
    )
    assert keywords == ["TCP/IPの仕組み", "3ウェイハンドシェイク", "再送制御", "輻輳制御", "SYN", "TCP"]
    assert source == _SOURCE.fingerprint


async def test_skips_the_llm_when_the_source_is_unchanged(
    db_conn: asyncpg.Connection, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = await _session(db_conn, test_user["id"])
    generator = _FakeGenerator()
    monkeypatch.setattr(transcription_keywords, "generate_terms", generator)
    await refresh_transcription_keywords(session_id, test_user["id"], _SOURCE)

    assert await refresh_transcription_keywords(session_id, test_user["id"], _SOURCE) is False
    assert len(generator.sources) == 1


async def test_regenerates_after_the_topic_changes(
    db_conn: asyncpg.Connection, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = await _session(db_conn, test_user["id"])
    generator = _FakeGenerator()
    monkeypatch.setattr(transcription_keywords, "generate_terms", generator)
    await refresh_transcription_keywords(session_id, test_user["id"], _SOURCE)

    corrected = KeywordSource("UDPの仕組み", ("ポート番号",), "")
    assert await refresh_transcription_keywords(session_id, test_user["id"], corrected) is True

    keywords, _ = await dialogue_session_repository.find_transcription_keywords(db_conn, session_id, test_user["id"])
    assert keywords is not None
    assert keywords[:2] == ["UDPの仕組み", "ポート番号"]


async def test_keeps_topic_and_aspects_and_retries_after_a_failure(
    db_conn: asyncpg.Connection, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = await _session(db_conn, test_user["id"])
    monkeypatch.setattr(transcription_keywords, "generate_terms", _FakeGenerator(fail=True))

    await refresh_transcription_keywords(session_id, test_user["id"], _SOURCE)

    keywords, source = await dialogue_session_repository.find_transcription_keywords(
        db_conn, session_id, test_user["id"]
    )
    assert keywords == ["TCP/IPの仕組み", "3ウェイハンドシェイク", "再送制御"]
    assert source == ""
    retry = _FakeGenerator()
    monkeypatch.setattr(transcription_keywords, "generate_terms", retry)
    assert await refresh_transcription_keywords(session_id, test_user["id"], _SOURCE) is True


async def test_reads_nothing_for_another_users_session(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _session(db_conn, test_user["id"])
    await dialogue_session_repository.update_transcription_keywords(db_conn, session_id, ["TCP"], "x")

    assert await dialogue_session_repository.find_transcription_keywords(db_conn, session_id, "someone-else") == (
        None,
        None,
    )
