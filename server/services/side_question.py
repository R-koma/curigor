import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID, uuid4

import anyio
import asyncpg
from fastapi import status
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from api.errors import DAILY_TURN_LIMIT_DETAIL, ApiError, ErrorCode
from core import config
from core.database import DBConnection, get_pool
from graph.llm import llm
from graph.prompts.side_question import (
    SIDE_QUESTION_PROMPT_FINGERPRINT,
    build_side_question_prompt,
    format_side_questions_for_context,
    format_side_thread,
)
from observability.langfuse_tracing import traced_side_question
from repositories import (
    dialogue_message_repository,
    dialogue_session_repository,
    llm_usage_repository,
    side_question_repository,
)
from schemas.side_question import (
    MAX_SIDE_DEPTH,
    SideQuestionCreate,
    SideStreamChunk,
    SideStreamEnd,
    SideStreamError,
    SideStreamStarted,
)

logger = logging.getLogger(__name__)

RECENT_MAIN_MESSAGES = 8
OTHER_SIDE_QUESTIONS_MAX_CHARS = 2000
_ACTIVE_STATUSES = ("in_progress", "disconnect")
_FAILED_DETAIL = "回答を作れませんでした。もう一度送ってください"
_ANCHOR_GONE_DETAIL = "質問した箇所の応答が取り消されました"


@dataclass
class SideTurn:
    session_id: UUID
    user_id: str
    side_question_id: UUID
    user_message_id: UUID
    answer_message_id: UUID
    quote: str
    llm_input: list[BaseMessage]


async def _active_explore_session(conn: DBConnection, session_id: UUID, user_id: str) -> dict[str, Any]:
    session = await dialogue_session_repository.find_by_id(conn, session_id, user_id)
    if session is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.SESSION_NOT_FOUND, "Session not found")
    if session["session_type"] != "explore":
        raise ApiError(status.HTTP_409_CONFLICT, ErrorCode.SESSION_NOT_EXPLORE, "Not an explore session")
    if session["status"] not in _ACTIVE_STATUSES:
        raise ApiError(status.HTTP_409_CONFLICT, ErrorCode.SESSION_NOT_ACTIVE, "Session is not in progress")
    return session


def _anchor_not_found() -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.SIDE_QUESTION_ANCHOR_NOT_FOUND, "Anchor not found")


async def _reserve_turn(conn: DBConnection, user_id: str) -> UUID:
    usage_id = await llm_usage_repository.reserve(
        conn, user_id, "turn", config.REVIEW_TIMEZONE, config.DAILY_TURN_LIMIT
    )
    if usage_id is None:
        raise ApiError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            ErrorCode.DAILY_TURN_LIMIT_REACHED,
            DAILY_TURN_LIMIT_DETAIL.format(limit=config.DAILY_TURN_LIMIT),
        )
    return usage_id


def _recent_messages(rows: Sequence[dict[str, Any]]) -> str:
    return "\n".join(
        f"{'ユーザー' if r['role'] == 'user' else 'AI'}: {r['content']}" for r in rows[-RECENT_MAIN_MESSAGES:]
    )


def _lineage(threads: Sequence[dict[str, Any]], thread_id: UUID) -> list[dict[str, Any]]:
    by_id = {t["id"]: t for t in threads}
    chain: list[dict[str, Any]] = []
    current = by_id.get(thread_id)
    while current is not None:
        chain.append(current)
        current = by_id.get(current["parent_id"]) if current["parent_id"] is not None else None
    return list(reversed(chain))


async def _anchor_text(conn: DBConnection, thread: dict[str, Any]) -> str:
    if thread["anchor_message_id"] is not None:
        row = await dialogue_message_repository.find_in_session(
            conn, thread["anchor_message_id"], thread["dialogue_session_id"]
        )
        return str(row["content"]) if row else ""
    owner = await side_question_repository.find_side_message_owner(conn, thread["anchor_side_message_id"])
    return str(owner["content"]) if owner else ""


async def _llm_input(
    conn: DBConnection, session: dict[str, Any], thread: dict[str, Any], content: str, user_message_id: UUID
) -> list[BaseMessage]:
    session_id: UUID = session["id"]
    threads = await side_question_repository.find_threads(conn, session_id)
    lineage = _lineage(threads, thread["id"])
    lineage_ids = {t["id"] for t in lineage} | {thread["id"]}
    ancestors = "\n\n".join(format_side_thread(t) for t in lineage if t["id"] != thread["id"])
    others = format_side_questions_for_context(
        [t for t in threads if t["id"] not in lineage_ids], max_chars=OTHER_SIDE_QUESTIONS_MAX_CHARS
    )
    main_rows = await dialogue_message_repository.find_by_session_id(conn, session_id)
    prompt = build_side_question_prompt(
        topic=str(session.get("topic") or ""),
        anchor_text=await _anchor_text(conn, thread),
        quote=thread["quote"],
        recent_messages=_recent_messages(main_rows),
        ancestors=ancestors,
        other_side_questions=others,
    )
    own = next((t for t in threads if t["id"] == thread["id"]), None)
    history: list[BaseMessage] = [
        HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"])
        for m in (own["messages"] if own else [])
        if m["id"] != user_message_id
    ]
    return [SystemMessage(content=prompt), *history, HumanMessage(content=content)]


async def _cancel_usage(conn: DBConnection, usage_id: UUID) -> None:
    await llm_usage_repository.cancel(conn, usage_id)


async def _abandon_unanswered(side_question_id: UUID, user_message_id: UUID, usage_id: UUID) -> None:
    with anyio.CancelScope(shield=True):
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await side_question_repository.delete_message(conn, user_message_id)
                await side_question_repository.delete_if_empty(conn, side_question_id)
                await _cancel_usage(conn, usage_id)
        except Exception:
            logger.exception("Failed to discard side question message %s", user_message_id)


async def _turn(
    session: dict[str, Any], thread: dict[str, Any], content: str, user_message_id: UUID, usage_id: UUID
) -> SideTurn:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            llm_input = await _llm_input(conn, session, thread, content, user_message_id)
    except BaseException:
        await _abandon_unanswered(thread["id"], user_message_id, usage_id)
        raise
    return SideTurn(
        session_id=thread["dialogue_session_id"],
        user_id=session["user_id"],
        side_question_id=thread["id"],
        user_message_id=user_message_id,
        answer_message_id=uuid4(),
        quote=thread["quote"],
        llm_input=llm_input,
    )


async def prepare_new(session_id: UUID, user_id: str, body: SideQuestionCreate) -> SideTurn:
    pool = await get_pool()
    async with pool.acquire() as conn:
        session = await _active_explore_session(conn, session_id, user_id)
        parent_id: UUID | None = None
        depth = 0
        if body.anchor_message_id is not None:
            row = await dialogue_message_repository.find_in_session(conn, body.anchor_message_id, session_id)
            if row is None or row["role"] != "assistant":
                raise _anchor_not_found()
        else:
            assert body.anchor_side_message_id is not None
            owner = await side_question_repository.find_side_message_owner(conn, body.anchor_side_message_id)
            if owner is None or owner["role"] != "assistant" or owner["dialogue_session_id"] != session_id:
                raise _anchor_not_found()
            if owner["depth"] >= MAX_SIDE_DEPTH:
                raise ApiError(
                    status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.SIDE_QUESTION_TOO_DEEP, "Too deeply nested"
                )
            parent_id = owner["id"]
            depth = owner["depth"] + 1
        usage_id = await _reserve_turn(conn, user_id)
        try:
            async with conn.transaction():
                thread = await side_question_repository.create(
                    conn,
                    dialogue_session_id=session_id,
                    parent_id=parent_id,
                    anchor_message_id=body.anchor_message_id,
                    anchor_side_message_id=body.anchor_side_message_id,
                    quote=body.quote,
                    occurrence=body.occurrence,
                    depth=depth,
                )
                user_message = await side_question_repository.add_message(conn, thread["id"], "user", body.content)
        except asyncpg.ForeignKeyViolationError as exc:
            await _cancel_usage(conn, usage_id)
            raise _anchor_not_found() from exc
    return await _turn(session, thread, body.content, user_message["id"], usage_id)


async def prepare_follow_up(side_question_id: UUID, user_id: str, content: str) -> SideTurn:
    pool = await get_pool()
    async with pool.acquire() as conn:
        thread = await side_question_repository.find_owned(conn, side_question_id, user_id)
        if thread is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.SIDE_QUESTION_NOT_FOUND, "Side question not found")
        session = await _active_explore_session(conn, thread["dialogue_session_id"], user_id)
        usage_id = await _reserve_turn(conn, user_id)
        try:
            user_message = await side_question_repository.add_message(conn, side_question_id, "user", content)
        except asyncpg.ForeignKeyViolationError as exc:
            await _cancel_usage(conn, usage_id)
            raise ApiError(
                status.HTTP_404_NOT_FOUND, ErrorCode.SIDE_QUESTION_NOT_FOUND, "Side question not found"
            ) from exc
    return await _turn(session, thread, content, user_message["id"], usage_id)


def _line(event: BaseModel) -> str:
    return event.model_dump_json() + "\n"


async def _discard(turn: SideTurn) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await side_question_repository.delete_message(conn, turn.user_message_id)
        await side_question_repository.delete_if_empty(conn, turn.side_question_id)


async def _discard_shielded(turn: SideTurn) -> None:
    with anyio.CancelScope(shield=True):
        try:
            await _discard(turn)
        except Exception:
            logger.exception("Failed to discard side question message %s", turn.user_message_id)


async def stream_answer(turn: SideTurn) -> AsyncIterator[str]:
    yield _line(
        SideStreamStarted(
            side_question_id=turn.side_question_id,
            user_message_id=turn.user_message_id,
            answer_message_id=turn.answer_message_id,
        )
    )
    answer = ""
    try:
        async with traced_side_question(session_id=turn.session_id, user_id=turn.user_id, quote=turn.quote) as run:
            llm_config = cast(
                RunnableConfig, {**run.config, "metadata": {"prompt_fingerprint": SIDE_QUESTION_PROMPT_FINGERPRINT}}
            )
            async for text in llm.astream(turn.llm_input, llm_config, task="explore-side-question"):
                answer += text
                yield _line(SideStreamChunk(content=text))
            run.set_output(answer)
        if not answer.strip():
            raise RuntimeError("The side question answer was empty")
        pool = await get_pool()
        async with pool.acquire() as conn:
            await side_question_repository.add_message(
                conn, turn.side_question_id, "assistant", answer, message_id=turn.answer_message_id
            )
    except asyncpg.ForeignKeyViolationError:
        await _discard_shielded(turn)
        yield _line(SideStreamError(code="side_question_anchor_gone", detail=_ANCHOR_GONE_DETAIL))
        return
    except Exception:
        logger.exception("Side question answer failed for session %s", turn.session_id)
        await _discard_shielded(turn)
        yield _line(SideStreamError(code="side_question_failed", detail=_FAILED_DETAIL))
        return
    except BaseException:
        await _discard_shielded(turn)
        raise
    yield _line(SideStreamEnd())
