import asyncio
import hashlib
import json
import logging
from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID

import asyncpg
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from core import config
from core.database import get_pool
from graph.aspect_map import parse_aspect_map
from graph.llm import llm_structured
from graph.output_schemas import ReviewPlanGeneration
from graph.prompts.review_plan import REVIEW_PLAN_PROMPT_FINGERPRINT, build_review_plan_prompt
from graph.review_plan import ReviewPlanPoint, ReviewResult, carryover_points, sanitize_plan_points
from observability.langfuse_tracing import traced_review_plan
from repositories import (
    feedback_repository,
    llm_usage_repository,
    note_repository,
    note_revision_repository,
    review_plan_repository,
    review_schedule_repository,
)

logger = logging.getLogger(__name__)

REVISIONS_HEADING = "## 復習での追記"

# asyncio はタスクを弱参照でしか持たないため、完了まで参照を保持する
_pending: set[asyncio.Task[None]] = set()
_locks: dict[UUID, asyncio.Lock] = {}


def plan_note_hash(content: str, revisions: Sequence[str]) -> str:
    return hashlib.sha256("\x00".join([content, *revisions]).encode()).hexdigest()


def _json_list(row: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    raw = (row or {}).get(key)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    return raw if isinstance(raw, list) else []


def _content_with_revisions(content: str, revisions: Sequence[str]) -> str:
    if not revisions:
        return content
    return f"{content}\n\n{REVISIONS_HEADING}\n" + "\n".join(revisions)


async def _generate(note_id: UUID, user_id: str) -> list[ReviewPlanPoint] | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        note = await note_repository.find_by_id(conn, note_id, user_id)
        if note is None:
            return None
        revisions = [r["content"] for r in await note_revision_repository.find_by_note_id(conn, note_id, user_id)]
        feedbacks = await feedback_repository.find_by_note_id(conn, note_id, user_id)
        plan = await review_plan_repository.find_by_note_id(conn, note_id, user_id)
        schedule = await review_schedule_repository.find_by_note_id(conn, note_id)

    latest = feedbacks[-1] if feedbacks else None
    results = cast(list[ReviewResult], _json_list(latest, "review_results"))
    carryover = carryover_points(plan["points"] if plan else None, results)
    aspect_map = parse_aspect_map(note["aspect_map"])
    prompt = build_review_plan_prompt(
        topic=note["topic"],
        summary=note["summary"] or "",
        content=_content_with_revisions(note["content"], revisions),
        aspect_map=aspect_map,
        improvements=_json_list(latest, "improvement_items"),
        carryover=carryover,
        previous_questions=[r["question"] for r in results if r["status"] != "not_asked"],
        explained=[r for r in results if r["status"] in ("explained", "explained_with_hint")],
        review_count=schedule["review_count"] if schedule else 0,
    )

    runnable = llm_structured.with_structured_output(ReviewPlanGeneration, task="generate-review-plan")
    async with traced_review_plan(user_id=user_id, note_id=note_id) as run:
        try:
            result: Any = await runnable.ainvoke(
                [SystemMessage(content=prompt)],
                config=cast(
                    RunnableConfig,
                    {
                        **run.config,
                        "run_name": "generate-review-plan",
                        "metadata": {"prompt_fingerprint": REVIEW_PLAN_PROMPT_FINGERPRINT},
                    },
                ),
            )
        except Exception:
            logger.warning("review plan generation failed for note %s", note_id, exc_info=True)
            return None
        if not isinstance(result, ReviewPlanGeneration):
            return None
        points = sanitize_plan_points(result.points, aspect_map, carryover)
        run.set_output({"points": len(points), "carryover": len(carryover)})

    if not points:
        return None
    async with pool.acquire() as conn:
        try:
            await review_plan_repository.upsert(
                conn,
                note_id,
                json.dumps(points, ensure_ascii=False),
                plan_note_hash(note["content"], revisions),
                REVIEW_PLAN_PROMPT_FINGERPRINT,
            )
        except asyncpg.ForeignKeyViolationError:
            return None
    return points


async def generate_review_plan(note_id: UUID, user_id: str) -> list[ReviewPlanPoint] | None:
    lock = _locks.setdefault(note_id, asyncio.Lock())
    async with lock:
        return await _generate(note_id, user_id)


async def _generate_quietly(note_id: UUID, user_id: str) -> None:
    try:
        await generate_review_plan(note_id, user_id)
    except Exception:
        logger.warning("review plan refresh failed for note %s", note_id, exc_info=True)


def schedule_review_plan(note_id: UUID, user_id: str) -> None:
    task = asyncio.create_task(_generate_quietly(note_id, user_id))
    _pending.add(task)
    task.add_done_callback(_pending.discard)


async def refresh_review_plan_after_edit(note_id: UUID, user_id: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        note = await note_repository.find_by_id(conn, note_id, user_id)
        if note is None:
            return
        revisions = [r["content"] for r in await note_revision_repository.find_by_note_id(conn, note_id, user_id)]
        plan = await review_plan_repository.find_by_note_id(conn, note_id, user_id)
        if (
            plan is not None
            and plan["note_content_hash"] == plan_note_hash(note["content"], revisions)
            and plan["prompt_fingerprint"] == REVIEW_PLAN_PROMPT_FINGERPRINT
        ):
            return
        usage_id = await llm_usage_repository.reserve(
            conn, user_id, "review_plan", config.REVIEW_TIMEZONE, config.DAILY_REVIEW_PLAN_EDIT_LIMIT
        )
    if usage_id is None:
        logger.info("review plan refresh for note %s skipped: daily edit limit reached", note_id)
        return
    await generate_review_plan(note_id, user_id)


async def _refresh_after_edit_quietly(note_id: UUID, user_id: str) -> None:
    try:
        await refresh_review_plan_after_edit(note_id, user_id)
    except Exception:
        logger.warning("review plan refresh after edit failed for note %s", note_id, exc_info=True)


def schedule_review_plan_after_edit(note_id: UUID, user_id: str) -> None:
    task = asyncio.create_task(_refresh_after_edit_quietly(note_id, user_id))
    _pending.add(task)
    task.add_done_callback(_pending.discard)
