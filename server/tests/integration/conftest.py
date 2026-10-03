import os
import subprocess
from collections.abc import AsyncGenerator
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

from core.database import DBConnection

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://learning_optimizer:localdev@localhost:5433/learning_optimizer_test",
)

SETUP_USER_TABLE_SQL = """--sql
CREATE TABLE IF NOT EXISTS "user" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "email" TEXT NOT NULL UNIQUE,
    "emailVerified" BOOLEAN NOT NULL,
    "createdAt" TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);
"""

SERVER_DIR = str(Path(__file__).resolve().parents[2])


@pytest.fixture(scope="session")
def _run_migrations() -> None:
    """同期 fixture でマイグレーションを実行（イベントループ不要）"""
    import asyncio

    async def _apply_better_auth() -> None:
        conn = await asyncpg.connect(TEST_DATABASE_URL)
        await conn.execute(SETUP_USER_TABLE_SQL)
        await conn.close()

    asyncio.run(_apply_better_auth())

    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        cwd=SERVER_DIR,
        check=True,
    )


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_pool(_run_migrations: None) -> AsyncGenerator[asyncpg.Pool]:
    pool = await asyncpg.create_pool(TEST_DATABASE_URL)
    assert pool is not None
    yield pool
    await pool.close()


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_db(test_pool: asyncpg.Pool) -> AsyncGenerator[None]:
    yield
    async with test_pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE TABLE transcription_usages, feedbacks, review_schedules, dialogue_messages, "
            "dialogue_sessions, notes, note_collections CASCADE"
        )


@pytest_asyncio.fixture(loop_scope="session")
async def db_conn(test_pool: asyncpg.Pool) -> AsyncGenerator[DBConnection]:
    async with test_pool.acquire() as conn:
        yield conn


@pytest_asyncio.fixture(loop_scope="session")
async def test_user(test_pool: asyncpg.Pool) -> dict[str, str]:
    """テスト用ユーザーを BetterAuth の user テーブルに作成する"""
    user = {
        "id": "test-user-001",
        "name": "Test User",
        "email": "test@example.com",
    }
    async with test_pool.acquire() as conn:
        await conn.execute(
            """--sql
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES ($1, $2, $3, true)
            ON CONFLICT (id) DO NOTHING
            """,
            user["id"],
            user["name"],
            user["email"],
        )
    return user
