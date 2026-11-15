from datetime import timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest

from repositories import (
    dialogue_message_repository,
    dialogue_session_repository,
    note_repository,
    study_memo_repository,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_create_persists_graph_version(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = uuid4()

    created = await dialogue_session_repository.create(
        conn=db_conn,
        session_id=session_id,
        user_id=test_user["id"],
        session_type="learning",
        graph_version=2,
    )

    assert created["graph_version"] == 2


async def test_find_by_id_returns_graph_version(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = uuid4()
    note_id = uuid4()
    await note_repository.insert(db_conn, note_id, test_user["id"], topic="t", content="c", summary="s")
    await dialogue_session_repository.create(
        conn=db_conn,
        session_id=session_id,
        user_id=test_user["id"],
        session_type="review",
        graph_version=2,
        note_id=note_id,
    )

    found = await dialogue_session_repository.find_by_id(db_conn, session_id, test_user["id"])

    assert found is not None
    assert found["graph_version"] == 2


async def test_create_defaults_note_id_to_null(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    created = await dialogue_session_repository.create(
        conn=db_conn,
        session_id=uuid4(),
        user_id=test_user["id"],
        session_type="learning",
        graph_version=2,
    )

    assert created["note_id"] is None


async def test_create_persists_note_id_for_review(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    note_id = uuid4()
    await note_repository.insert(db_conn, note_id, test_user["id"], topic="t", content="c", summary="s")

    created = await dialogue_session_repository.create(
        conn=db_conn,
        session_id=uuid4(),
        user_id=test_user["id"],
        session_type="review",
        graph_version=2,
        note_id=note_id,
    )

    assert created["note_id"] == note_id


async def _learning_session_with_first_message(db_conn: asyncpg.Connection, user_id: str) -> UUID:
    session_id = uuid4()
    await dialogue_session_repository.create(
        conn=db_conn, session_id=session_id, user_id=user_id, session_type="learning", graph_version=2
    )
    await dialogue_message_repository.insert(db_conn, session_id, "user", "仕事でReactのフックを使うので", 1)
    return session_id


async def test_topic_falls_back_to_first_user_message(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])

    found = await dialogue_session_repository.find_by_id(db_conn, session_id, test_user["id"])
    resumable = await dialogue_session_repository.find_resumable_by_user(db_conn, test_user["id"])

    assert found is not None and found["topic"] == "仕事でReactのフックを使うので"
    assert resumable is not None and resumable["topic"] == "仕事でReactのフックを使うので"


async def test_update_topic_overrides_first_message(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])

    await dialogue_session_repository.update_topic(db_conn, session_id, "React Hooks")

    found = await dialogue_session_repository.find_by_id(db_conn, session_id, test_user["id"])
    resumable = await dialogue_session_repository.find_resumable_by_user(db_conn, test_user["id"])
    assert found is not None and found["topic"] == "React Hooks"
    assert resumable is not None and resumable["topic"] == "React Hooks"


async def test_disconnect_does_not_overwrite_a_finished_session(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])
    await dialogue_session_repository.update_status(db_conn, session_id, "completed")

    await dialogue_session_repository.update_status(db_conn, session_id, "disconnect")

    found = await dialogue_session_repository.find_by_id(db_conn, session_id, test_user["id"])
    assert found is not None and found["status"] == "completed"
    assert await dialogue_session_repository.find_resumable_by_user(db_conn, test_user["id"]) is None


async def test_claiming_a_session_moves_it_to_the_new_connection(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])
    first, second = uuid4(), uuid4()
    assert await dialogue_session_repository.claim_connection(db_conn, session_id, test_user["id"], first)

    assert await dialogue_session_repository.claim_connection(db_conn, session_id, test_user["id"], second)

    assert not await dialogue_session_repository.is_held_by(db_conn, session_id, first)
    assert await dialogue_session_repository.is_held_by(db_conn, session_id, second)


async def test_claiming_reopens_a_disconnected_session(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])
    await dialogue_session_repository.update_status(db_conn, session_id, "disconnect")
    connection_id = uuid4()

    assert await dialogue_session_repository.claim_connection(db_conn, session_id, test_user["id"], connection_id)

    found = await dialogue_session_repository.find_by_id(db_conn, session_id, test_user["id"])
    assert found is not None and found["status"] == "in_progress"
    assert await dialogue_session_repository.is_held_by(db_conn, session_id, connection_id)


@pytest.mark.parametrize("status", ["completed", "abandoned", "generate_note"])
async def test_a_finished_session_cannot_be_claimed(
    db_conn: asyncpg.Connection, test_user: dict[str, str], status: str
) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])
    await dialogue_session_repository.update_status(db_conn, session_id, status)

    assert not await dialogue_session_repository.claim_connection(db_conn, session_id, test_user["id"], uuid4())

    found = await dialogue_session_repository.find_by_id(db_conn, session_id, test_user["id"])
    assert found is not None and found["status"] == status


async def test_another_user_cannot_claim_a_session(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])

    assert not await dialogue_session_repository.claim_connection(db_conn, session_id, "someone-else", uuid4())


async def test_a_released_connection_only_changes_a_session_it_still_holds(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])
    first, second = uuid4(), uuid4()
    await dialogue_session_repository.claim_connection(db_conn, session_id, test_user["id"], first)
    await dialogue_session_repository.claim_connection(db_conn, session_id, test_user["id"], second)

    await dialogue_session_repository.release_connection(db_conn, session_id, first, "disconnect")
    found = await dialogue_session_repository.find_by_id(db_conn, session_id, test_user["id"])
    assert found is not None and found["status"] == "in_progress"

    await dialogue_session_repository.release_connection(db_conn, session_id, second, "disconnect")
    found = await dialogue_session_repository.find_by_id(db_conn, session_id, test_user["id"])
    assert found is not None and found["status"] == "disconnect"


async def test_a_turn_is_in_flight_from_begin_until_finish(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])
    connection_id = uuid4()
    await dialogue_session_repository.claim_connection(db_conn, session_id, test_user["id"], connection_id)
    stale_after = timedelta(minutes=3)

    await dialogue_session_repository.begin_turn(db_conn, session_id, connection_id)
    assert await dialogue_session_repository.has_turn_in_flight(db_conn, session_id, stale_after)

    assert await dialogue_session_repository.finish_turn(db_conn, session_id, connection_id)
    assert not await dialogue_session_repository.has_turn_in_flight(db_conn, session_id, stale_after)


async def test_a_taken_over_connection_cannot_finish_its_turn(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])
    first, second = uuid4(), uuid4()
    await dialogue_session_repository.claim_connection(db_conn, session_id, test_user["id"], first)
    await dialogue_session_repository.begin_turn(db_conn, session_id, first)
    await dialogue_session_repository.claim_connection(db_conn, session_id, test_user["id"], second)

    assert not await dialogue_session_repository.finish_turn(db_conn, session_id, first)
    assert await dialogue_session_repository.has_turn_in_flight(db_conn, session_id, timedelta(minutes=3))

    await dialogue_session_repository.clear_turn(db_conn, session_id)
    assert not await dialogue_session_repository.has_turn_in_flight(db_conn, session_id, timedelta(minutes=3))


async def test_a_stale_turn_is_not_in_flight(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])
    await db_conn.execute(
        "UPDATE dialogue_sessions SET turn_started_at = NOW() - INTERVAL '10 minutes' WHERE id = $1", str(session_id)
    )

    assert not await dialogue_session_repository.has_turn_in_flight(db_conn, session_id, timedelta(minutes=3))


async def test_learning_session_with_a_note_is_not_resumable(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])
    note_id = uuid4()
    await note_repository.insert(db_conn, note_id, test_user["id"], topic="t", content="c", summary="s")
    await dialogue_session_repository.update_note_id(db_conn, session_id, note_id)
    await dialogue_session_repository.update_status(db_conn, session_id, "in_progress")

    assert await dialogue_session_repository.find_resumable_by_user(db_conn, test_user["id"]) is None


async def test_synthesis_sessions_are_never_resumable(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    await dialogue_session_repository.create(
        db_conn,
        session_id=uuid4(),
        user_id=test_user["id"],
        session_type="synthesis",
        graph_version=4,
        topic="Linuxのしくみ",
    )

    assert await dialogue_session_repository.find_resumable_by_user(db_conn, test_user["id"]) is None


async def test_abandon_active_by_user_leaves_synthesis_sessions_untouched(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    learning_id, synthesis_id = uuid4(), uuid4()
    for session_id, session_type in ((learning_id, "learning"), (synthesis_id, "synthesis")):
        await dialogue_session_repository.create(
            conn=db_conn,
            session_id=session_id,
            user_id=test_user["id"],
            session_type=session_type,
            graph_version=2,
        )

    await dialogue_session_repository.abandon_active_by_user(db_conn, test_user["id"])

    statuses = {
        r["id"]: r["status"]
        for r in await db_conn.fetch("SELECT id, status FROM dialogue_sessions WHERE user_id = $1", test_user["id"])
    }
    assert statuses[learning_id] == "abandoned"
    assert statuses[synthesis_id] == "in_progress"


async def test_explore_sessions_are_resumable(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = uuid4()
    await dialogue_session_repository.create(
        db_conn, session_id=session_id, user_id=test_user["id"], session_type="explore", graph_version=4
    )

    resumable = await dialogue_session_repository.find_resumable_by_user(db_conn, test_user["id"])

    assert resumable is not None
    assert resumable["id"] == session_id
    assert resumable["session_type"] == "explore"


async def test_create_stores_the_study_memo_and_it_is_cleared_when_the_memo_goes(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    user_id = test_user["id"]
    explore_id = uuid4()
    await dialogue_session_repository.create(
        db_conn, session_id=explore_id, user_id=user_id, session_type="explore", graph_version=4
    )
    memo_id = await study_memo_repository.insert(
        db_conn,
        user_id=user_id,
        dialogue_session_id=explore_id,
        topic="二分探索",
        source="",
        summary="",
        overview=[],
        glossary=[],
        questions=[],
        depth_map={"topic": "二分探索", "aspects": []},
    )
    learning_id = uuid4()
    await dialogue_session_repository.create(
        db_conn,
        session_id=learning_id,
        user_id=user_id,
        session_type="learning",
        graph_version=4,
        study_memo_id=memo_id,
    )

    found = await dialogue_session_repository.find_by_id(db_conn, learning_id, user_id)
    assert found is not None
    assert found["study_memo_id"] == memo_id

    await db_conn.execute("DELETE FROM study_memos WHERE id = $1", memo_id)
    after = await dialogue_session_repository.find_by_id(db_conn, learning_id, user_id)
    assert after is not None
    assert after["study_memo_id"] is None


async def test_generate_note_records_when_the_generation_started(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _learning_session_with_first_message(db_conn, test_user["id"])
    before = await db_conn.fetchval("SELECT generation_started_at FROM dialogue_sessions WHERE id = $1", session_id)

    await dialogue_session_repository.update_status(db_conn, session_id, "generate_note")

    started_at = await db_conn.fetchval(
        "SELECT generation_started_at FROM dialogue_sessions WHERE id = $1", session_id
    )
    assert before is None and started_at is not None
    now = await db_conn.fetchval("SELECT NOW()")
    assert now - started_at < timedelta(seconds=5)


async def test_reset_stuck_generations_leaves_a_fresh_generation_alone(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    fresh = await _learning_session_with_first_message(db_conn, test_user["id"])
    await dialogue_session_repository.update_status(db_conn, fresh, "generate_note")
    stale = await _learning_session_with_first_message(db_conn, test_user["id"])
    await dialogue_session_repository.update_status(db_conn, stale, "generate_note")
    await db_conn.execute(
        "UPDATE dialogue_sessions SET generation_started_at = NOW() - INTERVAL '4 minutes' WHERE id = $1", stale
    )
    legacy = await _learning_session_with_first_message(db_conn, test_user["id"])
    await db_conn.execute(
        "UPDATE dialogue_sessions SET status = 'generate_note', generation_started_at = NULL WHERE id = $1", legacy
    )
    completed = await _learning_session_with_first_message(db_conn, test_user["id"])
    await dialogue_session_repository.update_status(db_conn, completed, "completed")

    reset = await dialogue_session_repository.reset_stuck_generations(db_conn, timedelta(minutes=3))

    assert sorted(reset) == sorted([stale, legacy])
    statuses = {
        r["id"]: r["status"]
        for r in await db_conn.fetch(
            "SELECT id, status FROM dialogue_sessions WHERE id = ANY($1::uuid[])", [fresh, stale, legacy, completed]
        )
    }
    assert statuses == {fresh: "generate_note", stale: "failed", legacy: "failed", completed: "completed"}


_AGE_SQL = "SELECT NOW() - last_activity_at FROM dialogue_sessions WHERE id = $1"


async def _set_activity(db_conn: asyncpg.Connection, session_id: UUID, ago: timedelta) -> None:
    await db_conn.execute(
        "UPDATE dialogue_sessions SET last_activity_at = NOW() - $2::interval WHERE id = $1", session_id, ago
    )


async def _create_session(
    db_conn: asyncpg.Connection, user_id: str, session_type: str = "learning", status: str = "in_progress"
) -> UUID:
    session_id = uuid4()
    await dialogue_session_repository.create(
        db_conn, session_id=session_id, user_id=user_id, session_type=session_type, graph_version=2
    )
    if status != "in_progress":
        await db_conn.execute("UPDATE dialogue_sessions SET status = $2 WHERE id = $1", session_id, status)
    return session_id


async def test_find_saved_lists_unfinished_sessions_newest_first(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    learning = await _create_session(db_conn, test_user["id"], "learning", "disconnect")
    review = await _create_session(db_conn, test_user["id"], "review", "in_progress")
    explore = await _create_session(db_conn, test_user["id"], "explore", "disconnect")
    await _set_activity(db_conn, learning, timedelta(days=3))
    await _set_activity(db_conn, review, timedelta(days=1))
    await _set_activity(db_conn, explore, timedelta(days=2))

    saved = await dialogue_session_repository.find_saved_by_user(db_conn, test_user["id"])

    assert [row["id"] for row in saved] == [review, explore, learning]


async def test_find_saved_excludes_finished_synthesis_noted_learning_and_expired(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    await _create_session(db_conn, test_user["id"], "learning", "completed")
    await _create_session(db_conn, test_user["id"], "learning", "abandoned")
    await _create_session(db_conn, test_user["id"], "synthesis", "in_progress")
    noted = await _create_session(db_conn, test_user["id"], "learning", "disconnect")
    note_id = uuid4()
    await note_repository.insert(db_conn, note_id, test_user["id"], topic="t", content="c", summary="s")
    await db_conn.execute("UPDATE dialogue_sessions SET note_id = $2 WHERE id = $1", noted, note_id)
    expired = await _create_session(db_conn, test_user["id"], "learning", "disconnect")
    await _set_activity(db_conn, expired, timedelta(days=31))
    recent = await _create_session(db_conn, test_user["id"], "learning", "disconnect")
    await _set_activity(db_conn, recent, timedelta(days=29))

    saved = await dialogue_session_repository.find_saved_by_user(db_conn, test_user["id"])

    assert [row["id"] for row in saved] == [recent]


async def test_find_saved_returns_last_assistant_excerpt_truncated(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    with_reply = await _create_session(db_conn, test_user["id"])
    without_reply = await _create_session(db_conn, test_user["id"])
    await _set_activity(db_conn, without_reply, timedelta(days=1))
    long_reply = "あ" * 300
    await dialogue_message_repository.insert(db_conn, with_reply, "user", "質問", 1)
    await dialogue_message_repository.insert(db_conn, with_reply, "assistant", "最初の応答", 2)
    await dialogue_message_repository.insert(db_conn, with_reply, "assistant", long_reply, 3)
    await dialogue_message_repository.insert(db_conn, without_reply, "user", "質問", 1)

    saved = {row["id"]: row for row in await dialogue_session_repository.find_saved_by_user(db_conn, test_user["id"])}

    assert saved[with_reply]["last_assistant_excerpt"] == long_reply[:200]
    assert saved[without_reply]["last_assistant_excerpt"] is None


async def test_find_saved_other_users_sessions_not_listed(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    await db_conn.execute(
        """--sql
        INSERT INTO "user" (id, name, email, "emailVerified")
        VALUES ('other-saved-user', 'O', 'o-saved@example.com', true)
        ON CONFLICT (id) DO NOTHING
        """
    )
    await _create_session(db_conn, "other-saved-user")

    assert await dialogue_session_repository.find_saved_by_user(db_conn, test_user["id"]) == []


async def test_claim_connection_and_finish_turn_update_last_activity(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _create_session(db_conn, test_user["id"])
    connection_id = uuid4()
    await _set_activity(db_conn, session_id, timedelta(days=10))

    assert await dialogue_session_repository.claim_connection(db_conn, session_id, test_user["id"], connection_id)
    claimed_age = await db_conn.fetchval(
        "SELECT NOW() - last_activity_at FROM dialogue_sessions WHERE id = $1", session_id
    )
    assert claimed_age < timedelta(minutes=1)

    await _set_activity(db_conn, session_id, timedelta(days=10))
    assert await dialogue_session_repository.finish_turn(db_conn, session_id, connection_id)
    finished_age = await db_conn.fetchval(
        "SELECT NOW() - last_activity_at FROM dialogue_sessions WHERE id = $1", session_id
    )
    assert finished_age < timedelta(minutes=1)


async def test_claim_connection_refuses_expired_session(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    session_id = await _create_session(db_conn, test_user["id"], "learning", "disconnect")
    await _set_activity(db_conn, session_id, timedelta(days=31))

    assert not await dialogue_session_repository.claim_connection(db_conn, session_id, test_user["id"], uuid4())

    found = await dialogue_session_repository.find_by_id(db_conn, session_id, test_user["id"])
    assert found is not None and found["status"] == "disconnect"


async def test_record_progress_is_listed(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    session_id = await _create_session(db_conn, test_user["id"])

    await dialogue_session_repository.record_progress(db_conn, session_id, 2, 5)

    [row] = await dialogue_session_repository.find_saved_by_user(db_conn, test_user["id"])
    assert row["progress_reached"] == 2
    assert row["progress_target"] == 5
