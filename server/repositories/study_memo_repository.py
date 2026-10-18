import json
from typing import Any, TypedDict
from uuid import UUID

import asyncpg

from core.database import DBConnection

_JSON_COLUMNS = ("overview", "glossary", "questions", "depth_map")


class MemoOrigin(TypedDict):
    note_id: str
    feedback_id: str
    improvement_index: int
    improvement: str
    aspect_id: str | None


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
    summary: str,
    overview: list[dict[str, Any]],
    glossary: list[dict[str, str]],
    questions: list[dict[str, str]],
    depth_map: dict[str, Any],
    origin: MemoOrigin | None = None,
) -> UUID:
    record = await conn.fetchrow(
        """--sql
        INSERT INTO study_memos (
            user_id, dialogue_session_id, topic, source, summary, overview, glossary, questions, depth_map,
            origin_note_id, origin_feedback_id, origin_improvement_index, origin_improvement, origin_aspect_id
        )
        VALUES (
            $1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8::jsonb, $9::jsonb,
            (SELECT id FROM notes WHERE id = $10 AND user_id = $1),
            (SELECT id FROM feedbacks WHERE id = $11),
            $12, $13, $14
        )
        RETURNING id
        """,
        user_id,
        str(dialogue_session_id),
        topic,
        source,
        summary,
        json.dumps(overview, ensure_ascii=False),
        json.dumps(glossary, ensure_ascii=False),
        json.dumps(questions, ensure_ascii=False),
        json.dumps(depth_map, ensure_ascii=False),
        UUID(origin["note_id"]) if origin else None,
        UUID(origin["feedback_id"]) if origin else None,
        origin["improvement_index"] if origin else None,
        origin["improvement"] if origin else None,
        origin["aspect_id"] if origin else None,
    )
    assert record is not None
    return UUID(str(record["id"]))


_DETAIL_COLUMNS = (
    "id, dialogue_session_id, topic, source, summary, overview, glossary, questions, depth_map, created_at"
)


async def find_by_id(conn: DBConnection, memo_id: UUID, user_id: str) -> dict[str, Any] | None:
    record = await conn.fetchrow(
        """--sql
        SELECT m.id, m.dialogue_session_id, m.topic, m.source, m.summary, m.overview, m.glossary, m.questions,
               m.depth_map, m.created_at,
               m.origin_note_id, m.origin_feedback_id, m.origin_improvement_index, m.origin_improvement,
               m.origin_aspect_id, n.topic AS origin_note_topic
        FROM study_memos m
        LEFT JOIN notes n ON n.id = m.origin_note_id
        WHERE m.id = $1 AND m.user_id = $2
        """,
        memo_id,
        user_id,
    )
    return _decode(record) if record else None


async def find_by_id_for_update(conn: DBConnection, memo_id: UUID, user_id: str) -> dict[str, Any] | None:
    record = await conn.fetchrow(
        f"SELECT {_DETAIL_COLUMNS} FROM study_memos WHERE id = $1 AND user_id = $2 FOR UPDATE",  # noqa: S608
        memo_id,
        user_id,
    )
    return _decode(record) if record else None


_EDITABLE_COLUMNS = ("topic", "summary", "overview", "glossary", "questions")


async def update(conn: DBConnection, memo_id: UUID, user_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
    columns = [c for c in _EDITABLE_COLUMNS if c in changes]
    if not columns:
        return await find_by_id(conn, memo_id, user_id)
    assignments = ", ".join(
        f"{c} = ${i}::jsonb" if c in _JSON_COLUMNS else f"{c} = ${i}" for i, c in enumerate(columns, start=3)
    )
    values = [json.dumps(changes[c], ensure_ascii=False) if c in _JSON_COLUMNS else changes[c] for c in columns]
    record = await conn.fetchrow(
        f"UPDATE study_memos SET {assignments} WHERE id = $1 AND user_id = $2 RETURNING {_DETAIL_COLUMNS}",  # noqa: S608
        memo_id,
        user_id,
        *values,
    )
    return _decode(record) if record else None


async def delete(conn: DBConnection, memo_id: UUID, user_id: str) -> bool:
    result = await conn.execute("DELETE FROM study_memos WHERE id = $1 AND user_id = $2", memo_id, user_id)
    return result == "DELETE 1"


async def find_unorganized(conn: DBConnection) -> list[dict[str, Any]]:
    records = await conn.fetch(
        """--sql
        SELECT id, user_id, topic, overview, glossary, questions, depth_map
        FROM study_memos
        WHERE summary = ''
          AND jsonb_array_length(depth_map -> 'aspects') > 0
          AND jsonb_array_length(questions) + jsonb_array_length(glossary) > 0
          AND NOT EXISTS (
              SELECT 1
              FROM jsonb_array_elements(overview) a
              WHERE jsonb_array_length(COALESCE(a -> 'question_indices', '[]')) > 0
                 OR jsonb_array_length(COALESCE(a -> 'term_indices', '[]')) > 0
          )
        ORDER BY created_at
        """
    )
    return [_decode(r) for r in records]


async def find_by_session_id(conn: DBConnection, dialogue_session_id: UUID, user_id: str) -> dict[str, Any] | None:
    record = await conn.fetchrow(
        f"SELECT {_DETAIL_COLUMNS} FROM study_memos WHERE dialogue_session_id = $1 AND user_id = $2",  # noqa: S608
        str(dialogue_session_id),
        user_id,
    )
    return _decode(record) if record else None


async def find_by_user_id(conn: DBConnection, user_id: str) -> list[dict[str, Any]]:
    records = await conn.fetch(
        """--sql
        SELECT
            m.id, m.topic, m.source, m.created_at, m.overview, m.origin_note_id,
            jsonb_array_length(m.glossary) AS glossary_count,
            jsonb_array_length(m.questions) AS question_count,
            CASE
                WHEN m.origin_note_id IS NOT NULL THEN EXISTS (
                    SELECT 1
                    FROM feedbacks f
                    WHERE f.note_id = m.origin_note_id
                      AND f.created_at > m.created_at
                )
                ELSE EXISTS (
                SELECT 1
                FROM dialogue_sessions s
                WHERE s.study_memo_id = m.id
                  AND s.user_id = m.user_id
                  AND s.session_type = 'learning'
                  AND s.status = 'completed'
                  AND s.note_id IS NOT NULL
                )
            END AS handed_over
        FROM study_memos m
        WHERE m.user_id = $1
        ORDER BY m.created_at DESC, m.id DESC
        """,
        user_id,
    )
    return [_decode(r) for r in records]


async def find_by_origin_note(conn: DBConnection, note_id: UUID, user_id: str) -> list[dict[str, Any]]:
    records = await conn.fetch(
        """--sql
        SELECT id, topic, created_at, origin_feedback_id, origin_improvement_index, origin_improvement,
               origin_aspect_id
        FROM study_memos
        WHERE origin_note_id = $1 AND user_id = $2
        ORDER BY created_at DESC, id DESC
        """,
        note_id,
        user_id,
    )
    return [dict(r) for r in records]


async def find_priority_aspect_ids(conn: DBConnection, feedback_id: UUID, user_id: str) -> list[str]:
    records = await conn.fetch(
        """--sql
        SELECT DISTINCT origin_aspect_id
        FROM study_memos
        WHERE origin_feedback_id = $1 AND user_id = $2 AND origin_aspect_id IS NOT NULL
        ORDER BY origin_aspect_id
        """,
        feedback_id,
        user_id,
    )
    return [r["origin_aspect_id"] for r in records]
