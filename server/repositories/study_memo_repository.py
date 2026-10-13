import json
from typing import Any
from uuid import UUID

import asyncpg

from core.database import DBConnection

_JSON_COLUMNS = ("overview", "glossary", "questions", "depth_map")


def _decode(record: asyncpg.Record) -> dict[str, Any]:
    row = dict(record)
    for column in _JSON_COLUMNS:
        if isinstance(row.get(column), str):
            row[column] = json.loads(row[column])
    return row


async def insert(
    conn: DBConnection,
    *,
    user_id: str,
    dialogue_session_id: UUID | str,
    topic: str,
    source: str,
    overview: list[dict[str, Any]],
    glossary: list[dict[str, str]],
    questions: list[dict[str, str]],
    depth_map: dict[str, Any],
) -> UUID:
    record = await conn.fetchrow(
        """--sql
        INSERT INTO study_memos (
            user_id, dialogue_session_id, topic, source, overview, glossary, questions, depth_map
        )
        VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb, $8::jsonb)
        RETURNING id
        """,
        user_id,
        str(dialogue_session_id),
        topic,
        source,
        json.dumps(overview, ensure_ascii=False),
        json.dumps(glossary, ensure_ascii=False),
        json.dumps(questions, ensure_ascii=False),
        json.dumps(depth_map, ensure_ascii=False),
    )
    assert record is not None
    return UUID(str(record["id"]))


_DETAIL_COLUMNS = "id, dialogue_session_id, topic, source, overview, glossary, questions, depth_map, created_at"


async def find_by_id(conn: DBConnection, memo_id: UUID, user_id: str) -> dict[str, Any] | None:
    record = await conn.fetchrow(
        f"SELECT {_DETAIL_COLUMNS} FROM study_memos WHERE id = $1 AND user_id = $2", memo_id, user_id
    )
    return _decode(record) if record else None


async def find_by_session_id(conn: DBConnection, dialogue_session_id: UUID, user_id: str) -> dict[str, Any] | None:
    record = await conn.fetchrow(
        f"SELECT {_DETAIL_COLUMNS} FROM study_memos WHERE dialogue_session_id = $1 AND user_id = $2",
        str(dialogue_session_id),
        user_id,
    )
    return _decode(record) if record else None


async def find_by_user_id(conn: DBConnection, user_id: str) -> list[dict[str, Any]]:
    records = await conn.fetch(
        """--sql
        SELECT id, topic, source, created_at
        FROM study_memos
        WHERE user_id = $1
        ORDER BY created_at DESC, id DESC
        """,
        user_id,
    )
    return [dict(r) for r in records]
