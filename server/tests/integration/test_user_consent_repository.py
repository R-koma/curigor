import asyncpg
import pytest

from repositories import user_consent_repository

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_records_consent_to_a_version(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    assert not await user_consent_repository.has_consented(db_conn, test_user["id"], 1)

    await user_consent_repository.record(db_conn, test_user["id"], 1)

    assert await user_consent_repository.has_consented(db_conn, test_user["id"], 1)


async def test_consent_to_an_older_version_does_not_count(
    db_conn: asyncpg.Connection, test_user: dict[str, str]
) -> None:
    await user_consent_repository.record(db_conn, test_user["id"], 1)

    assert not await user_consent_repository.has_consented(db_conn, test_user["id"], 2)


async def test_keeps_every_version_consented_to(db_conn: asyncpg.Connection, test_user: dict[str, str]) -> None:
    await user_consent_repository.record(db_conn, test_user["id"], 1)
    await user_consent_repository.record(db_conn, test_user["id"], 2)
    await user_consent_repository.record(db_conn, test_user["id"], 2)

    rows = await db_conn.fetch(
        "SELECT terms_version FROM user_consents WHERE user_id = $1 ORDER BY terms_version", test_user["id"]
    )
    assert [row["terms_version"] for row in rows] == [1, 2]


async def test_deleting_the_user_removes_the_consents(db_conn: asyncpg.Connection) -> None:
    user_id = "consent-deleted-user"
    await db_conn.execute(
        """--sql
        INSERT INTO "user" (id, name, email, "emailVerified")
        VALUES ($1, 'c', 'consent-deleted@example.test', true)
        """,
        user_id,
    )
    await user_consent_repository.record(db_conn, user_id, 1)

    await db_conn.execute('DELETE FROM "user" WHERE id = $1', user_id)

    assert await db_conn.fetchval("SELECT COUNT(*) FROM user_consents WHERE user_id = $1", user_id) == 0
