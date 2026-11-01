import json
from datetime import date, datetime
from typing import Any

import asyncpg

from core.database import DBConnection

_JSON_COLUMNS = ("improvement_items", "review_results", "questions")


def _decode(record: asyncpg.Record) -> dict[str, Any]:
    row = dict(record)
    for column in _JSON_COLUMNS:
        if isinstance(row.get(column), str):
            row[column] = json.loads(row[column])
    return row


async def find_items_in_range(
    conn: DBConnection, user_id: str, start: date, end_exclusive: date, timezone: str
) -> list[dict[str, Any]]:
    query = """--sql
    WITH items AS (
        SELECT s.id AS session_id, s.session_type, s.ended_at AS finished_at,
               n.id AS note_id, NULL::uuid AS memo_id, n.topic, n.summary,
               f.improvement_items, f.improvements, f.review_results, NULL::jsonb AS questions
        FROM dialogue_sessions s
        JOIN notes n ON n.id = s.note_id AND n.user_id = s.user_id
        LEFT JOIN LATERAL (
            SELECT improvement_items, improvements, review_results
            FROM feedbacks
            WHERE dialogue_session_id = s.id
            ORDER BY created_at DESC
            LIMIT 1
        ) f ON TRUE
        WHERE s.user_id = $1
          AND s.session_type IN ('learning', 'review')
          AND s.status = 'completed'
          AND s.is_trial = false
          AND s.ended_at IS NOT NULL
        UNION ALL
        SELECT s.id, s.session_type, m.created_at,
               NULL::uuid, m.id, m.topic, m.summary,
               NULL::jsonb, NULL::text, NULL::jsonb, m.questions
        FROM dialogue_sessions s
        JOIN study_memos m ON m.dialogue_session_id = s.id AND m.user_id = s.user_id
        WHERE s.user_id = $1
          AND s.session_type = 'explore'
          AND s.status = 'completed'
          AND s.is_trial = false
    )
    SELECT *, (finished_at AT TIME ZONE $4)::date AS day
    FROM items
    WHERE (finished_at AT TIME ZONE $4)::date >= $2
      AND (finished_at AT TIME ZONE $4)::date < $3
    ORDER BY finished_at ASC
    """
    records = await conn.fetch(query, user_id, start, end_exclusive, timezone)
    return [_decode(r) for r in records]


async def find_viewed_at(conn: DBConnection, user_id: str, start: date, end_exclusive: date) -> dict[date, datetime]:
    records = await conn.fetch(
        """--sql
        SELECT day, viewed_at FROM reflection_views
        WHERE user_id = $1 AND day >= $2 AND day < $3
        """,
        user_id,
        start,
        end_exclusive,
    )
    return {r["day"]: r["viewed_at"] for r in records}


async def mark_viewed(conn: DBConnection, user_id: str, day: date) -> None:
    await conn.execute(
        """--sql
        INSERT INTO reflection_views (user_id, day, viewed_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (user_id, day) DO UPDATE SET viewed_at = NOW()
        """,
        user_id,
        day,
    )


async def find_generation(
    conn: DBConnection, user_id: str, period: str, start_date: date, kind: str
) -> dict[str, Any] | None:
    query = """--sql
    SELECT content_hash, payload
    FROM reflection_generations
    WHERE user_id = $1 AND period = $2 AND start_date = $3 AND kind = $4
    """
    record = await conn.fetchrow(query, user_id, period, start_date, kind)
    if record is None:
        return None
    row = dict(record)
    if isinstance(row["payload"], str):
        row["payload"] = json.loads(row["payload"])
    return row


async def upsert_generation(
    conn: DBConnection,
    *,
    user_id: str,
    period: str,
    start_date: date,
    kind: str,
    content_hash: str,
    payload: dict[str, Any],
) -> None:
    query = """--sql
    INSERT INTO reflection_generations (user_id, period, start_date, kind, content_hash, payload)
    VALUES ($1, $2, $3, $4, $5, $6::jsonb)
    ON CONFLICT (user_id, period, start_date, kind)
    DO UPDATE SET content_hash = EXCLUDED.content_hash, payload = EXCLUDED.payload, generated_at = NOW()
    """
    await conn.execute(query, user_id, period, start_date, kind, content_hash, json.dumps(payload, ensure_ascii=False))
