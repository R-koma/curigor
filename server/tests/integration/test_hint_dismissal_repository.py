import asyncpg
import pytest

from repositories import hint_dismissal_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_records_dismissed_hints(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    await hint_dismissal_repository.dismiss(db_conn, test_user["id"], "dashboard")
    await hint_dismissal_repository.dismiss(db_conn, test_user["id"], "chat_input")

    assert await hint_dismissal_repository.find_hint_ids_by_user(db_conn, test_user["id"]) == [
        "chat_input",
        "dashboard",
    ]


async def test_dismissing_twice_keeps_one_row(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    await hint_dismissal_repository.dismiss(db_conn, test_user["id"], "dashboard")
    await hint_dismissal_repository.dismiss(db_conn, test_user["id"], "dashboard")

    assert await hint_dismissal_repository.find_hint_ids_by_user(db_conn, test_user["id"]) == ["dashboard"]


async def test_reset_removes_only_the_users_rows(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    other_user_id = "hint-other-user"
    await db_conn.execute(
        """--sql
        INSERT INTO "user" (id, name, email, "emailVerified")
        VALUES ($1, 'other', 'hint-other@example.test', true)
        ON CONFLICT (id) DO NOTHING
        """,
        other_user_id,
    )
    await hint_dismissal_repository.dismiss(db_conn, test_user["id"], "dashboard")
    await hint_dismissal_repository.dismiss(db_conn, other_user_id, "dashboard")

    await hint_dismissal_repository.delete_all_by_user(db_conn, test_user["id"])

    assert await hint_dismissal_repository.find_hint_ids_by_user(db_conn, test_user["id"]) == []
    assert await hint_dismissal_repository.find_hint_ids_by_user(db_conn, other_user_id) == ["dashboard"]
