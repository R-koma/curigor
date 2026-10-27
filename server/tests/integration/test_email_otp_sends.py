import asyncio
from collections.abc import AsyncGenerator
from uuid import UUID

import asyncpg
import pytest
import pytest_asyncio

from core.database import DBConnection

pytestmark = pytest.mark.asyncio(loop_scope="session")

_RESERVE = "SELECT send_id, retry_after_seconds FROM reserve_email_otp_send($1, $2, $3, $4, $5)"


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_sends(test_pool: asyncpg.Pool) -> AsyncGenerator[None]:
    yield
    async with test_pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE email_otp_sends")


async def _reserve(
    conn: DBConnection,
    email: str = "email-a",
    ip: str | None = "ip-a",
    *,
    ip_hourly: int = 10,
    email_hourly: int = 5,
    email_daily: int = 10,
) -> tuple[UUID | None, int | None]:
    row = await conn.fetchrow(_RESERVE, email, ip, ip_hourly, email_hourly, email_daily)
    assert row is not None
    return row["send_id"], row["retry_after_seconds"]


async def _backdate(conn: DBConnection, interval: str) -> None:
    await conn.execute(f"UPDATE email_otp_sends SET created_at = created_at - INTERVAL '{interval}'")  # noqa: S608


async def test_reserves_under_the_limits(db_conn: asyncpg.Connection) -> None:
    send_id, retry_after = await _reserve(db_conn)

    assert send_id is not None
    assert retry_after is None
    assert await db_conn.fetchval("SELECT COUNT(*) FROM email_otp_sends") == 1


async def test_refuses_the_same_address_over_the_hourly_limit(db_conn: asyncpg.Connection) -> None:
    for i in range(2):
        await _reserve(db_conn, ip=f"ip-{i}", email_hourly=2)

    send_id, retry_after = await _reserve(db_conn, ip="ip-other", email_hourly=2)

    assert send_id is None
    assert retry_after is not None
    assert 3500 < retry_after <= 3600
    assert await db_conn.fetchval("SELECT COUNT(*) FROM email_otp_sends") == 2


async def test_hourly_address_limit_frees_up_after_an_hour(db_conn: asyncpg.Connection) -> None:
    for _ in range(2):
        await _reserve(db_conn, email_hourly=2)
    await _backdate(db_conn, "61 minutes")

    send_id, _ = await _reserve(db_conn, email_hourly=2)

    assert send_id is not None


async def test_refuses_the_same_address_over_the_daily_limit(db_conn: asyncpg.Connection) -> None:
    for _ in range(3):
        await _reserve(db_conn, email_daily=3)
    await _backdate(db_conn, "2 hours")

    send_id, retry_after = await _reserve(db_conn, email_daily=3)

    assert send_id is None
    assert retry_after is not None
    assert 22 * 3600 - 60 < retry_after <= 22 * 3600


async def test_refuses_the_same_ip_over_the_hourly_limit(db_conn: asyncpg.Connection) -> None:
    for i in range(2):
        await _reserve(db_conn, email=f"email-{i}", ip_hourly=2)

    send_id, retry_after = await _reserve(db_conn, email="email-other", ip_hourly=2)

    assert send_id is None
    assert retry_after is not None


async def test_skips_the_ip_limit_without_an_ip(db_conn: asyncpg.Connection) -> None:
    for i in range(3):
        send_id, _ = await _reserve(db_conn, email=f"email-{i}", ip=None, ip_hourly=1)
        assert send_id is not None


async def test_deletes_records_older_than_a_day(db_conn: asyncpg.Connection) -> None:
    await _reserve(db_conn, email="email-old")
    await _backdate(db_conn, "25 hours")

    await _reserve(db_conn, email="email-new")

    assert await db_conn.fetchval("SELECT COUNT(*) FROM email_otp_sends") == 1


async def test_concurrent_requests_do_not_exceed_the_limit(test_pool: asyncpg.Pool) -> None:
    async def reserve_once() -> UUID | None:
        async with test_pool.acquire() as conn:
            send_id, _ = await _reserve(conn, email_hourly=3)
            return send_id

    results = await asyncio.gather(*(reserve_once() for _ in range(10)))

    assert sum(result is not None for result in results) == 3
