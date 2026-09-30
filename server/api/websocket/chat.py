import asyncio
import base64
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Literal, cast
from uuid import UUID

import asyncpg
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import AIMessageChunk, HumanMessage, RemoveMessage
from pydantic import BaseModel, TypeAdapter, ValidationError

from api.websocket.auth import authenticate_websocket
from core.database import DBConnection, get_pool
from graph.coverage import coverage_progress
from graph.depth_map import depth_map_progress
from graph.llm import INTERNAL_LLM_TAG
from graph.multimodal import image_attachments_kwargs
from graph.version import GRAPH_VERSION
from observability.langfuse_tracing import build_graph_config, traced_graph_run
from repositories import (
    dialogue_message_image_repository,
    dialogue_message_repository,
    dialogue_session_repository,
    feedback_repository,
    note_repository,
)
from schemas.intake_card import IntakeCard
from schemas.websocket_message import (
    AssistantMessageChunk,
    AssistantMessageEnd,
    CancelLastMessageError,
    CancelLastMessageRequest,
    CancelLastMessageSuccess,
    EndSessionMessage,
    ErrorMessage,
    FeedbackGeneratedMessage,
    ImageAttachment,
    IncomingMessage,
    IntakeQuestionMessage,
    LearningProgress,
    NoteGeneratedMessage,
    PendingMessageRolledBack,
    ResumeSessionMessage,
    SessionEndedMessage,
    SessionResumedMessage,
    SessionStartedMessage,
    StartLearningMessage,
    StartReviewMessage,
    UserMessage,
)
from storage import get_storage

logger = logging.getLogger(__name__)

_MIME_TO_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

_STREAMING_NODES = {"learning_start", "learning_dialogue", "review_start", "review_dialogue"}
MIN_TURNS_BEFORE_NOTE = 3

_incoming_adapter: TypeAdapter[IncomingMessage] = TypeAdapter(IncomingMessage)


@dataclass
class SessionContext:
    session_id: UUID
    config: dict[str, Any]
    session_type: Literal["learning", "review"]
    message_order: int
    is_session_ended: bool = False


@dataclass
class Deps:
    pool: asyncpg.Pool
    graph: Any
    websocket: WebSocket
    user_id: str


async def _generate_note_background(
    pool: asyncpg.Pool,
    graph: Any,
    config: dict[str, Any],
    session_id: UUID,
    run_name: str,
) -> None:
    try:
        async with traced_graph_run(
            config,
            name=run_name,
            input={"dialogue_session_id": str(session_id)},
            as_type="chain",
        ) as run:
            result = await graph.ainvoke(None, config=run.config)
            run.set_output({"note_id": str(result.get("note_id")), "topic": result.get("topic")})
        generated_note_id: UUID | None = result.get("note_id")
        async with pool.acquire() as conn:
            if generated_note_id is not None:
                await dialogue_session_repository.update_note_id(conn, session_id, generated_note_id)
            else:
                await dialogue_session_repository.update_status(conn, session_id, "completed")
    except Exception:
        logger.exception("Background note generation failed for session %s", session_id)
        async with pool.acquire() as conn:
            await dialogue_session_repository.update_status(conn, session_id, "failed")


async def _learning_progress(graph: Any, config: dict[str, Any]) -> LearningProgress | None:
    """進捗は表示専用の副次情報。取得に失敗してもターンの成否に影響させず `None` を返す。"""
    try:
        values = (await graph.aget_state(config)).values
    except Exception:
        logger.exception("Failed to read learning progress")
        return None
    depth_map = values.get("depth_map")
    if depth_map:
        progress = depth_map_progress(values.get("map_covered") or [], depth_map)
    else:
        progress = coverage_progress(values.get("covered_aspects") or [], values.get("focus_aspects"))
    return LearningProgress(
        reached_aspects=list(progress.reached_aspects),
        target_count=progress.target_count,
        is_complete=progress.is_complete,
    )


async def _intake_question(graph: Any, config: dict[str, Any]) -> IntakeQuestionMessage | None:
    try:
        values = (await graph.aget_state(config)).values
    except Exception:
        logger.exception("Failed to read intake card")
        return None
    messages = values.get("messages") or []
    if not messages or messages[-1].type != "ai":
        return None
    card = messages[-1].additional_kwargs.get("intake_card")
    if card is None:
        return None
    return IntakeQuestionMessage(
        content=str(messages[-1].content),
        card=IntakeCard.model_validate(card),
        topic=str(values.get("topic") or ""),
    )


async def _stream_ai_response(
    graph: Any,
    input: Any,
    config: dict[str, Any],
    websocket: WebSocket,
    *,
    progress_config: dict[str, Any] | None = None,
) -> str:
    ai_content = ""
    async for msg, metadata in graph.astream(input, config, stream_mode="messages"):
        node = metadata.get("langgraph_node", "")
        if INTERNAL_LLM_TAG in (metadata.get("tags") or []):
            continue
        if isinstance(msg, AIMessageChunk) and node in _STREAMING_NODES and msg.content:
            chunk = str(msg.content)
            ai_content += chunk
            await websocket.send_text(AssistantMessageChunk(content=chunk).model_dump_json())
    if progress_config is not None and not ai_content:
        question = await _intake_question(graph, progress_config)
        if question is not None:
            await websocket.send_text(question.model_dump_json())
            ai_content = question.content
    progress = await _learning_progress(graph, progress_config) if progress_config is not None else None
    await websocket.send_text(AssistantMessageEnd(progress=progress).model_dump_json())
    return ai_content


async def _start_session(
    *,
    session_type: Literal["learning", "review"],
    deps: Deps,
    initial_state: dict[str, Any],
    first_user_content: str,
    note_id: UUID | None = None,
) -> SessionContext:
    """セッション作成・SessionStarted 送信・初期 user/assistant メッセージ保存までを共通化。"""
    session_id = uuid.uuid4()
    config = build_graph_config(session_id=session_id, user_id=deps.user_id, session_type=session_type)

    message_order = 1
    async with deps.pool.acquire() as conn:
        await dialogue_session_repository.abandon_active_by_user(conn, deps.user_id)
        await dialogue_session_repository.create(
            conn=conn,
            session_id=session_id,
            user_id=deps.user_id,
            session_type=session_type,
            graph_version=GRAPH_VERSION,
            note_id=note_id,
        )
        await dialogue_message_repository.insert(
            conn, session_id, "user", first_user_content, message_order, client_message_id=None
        )

    await deps.websocket.send_text(
        SessionStartedMessage(session_id=session_id, session_type=session_type).model_dump_json()
    )

    initial_state["dialogue_session_id"] = str(session_id)

    async with traced_graph_run(config, name=f"start-{session_type}-session", input=first_user_content) as run:
        ai_msg = await _stream_ai_response(
            deps.graph,
            initial_state,
            run.config,
            deps.websocket,
            progress_config=config if session_type == "learning" else None,
        )
        run.set_output(ai_msg)

    question = await _intake_question(deps.graph, config) if session_type == "learning" else None

    message_order += 1
    async with deps.pool.acquire() as conn:
        await dialogue_message_repository.insert(
            conn,
            session_id,
            "assistant",
            ai_msg,
            message_order,
            client_message_id=None,
            intake_card=question.card.model_dump_json() if question else None,
        )
        if question is not None and question.topic:
            await dialogue_session_repository.update_topic(conn, session_id, question.topic)

    return SessionContext(
        session_id=session_id,
        config=config,
        session_type=session_type,
        message_order=message_order,
    )


async def _finalize_session(result: dict[str, Any], ctx: SessionContext, deps: Deps) -> list[BaseModel]:
    """ノート生成完了時にクライアントへ送るメッセージ列を返す（送信順）。"""
    outgoing: list[BaseModel] = []
    note_id: UUID | None = result.get("note_id")
    if note_id is None:
        return outgoing

    async with deps.pool.acquire() as conn:
        await dialogue_session_repository.update_note_id(conn, ctx.session_id, note_id)

        if ctx.session_type == "review":
            feedbacks = await feedback_repository.find_by_note_id(conn, note_id, deps.user_id)
            if feedbacks:
                latest = feedbacks[-1]
                outgoing.append(
                    FeedbackGeneratedMessage(
                        understanding_level=latest["understanding_level"],
                        strength=latest["strength"],
                        improvements=latest["improvements"],
                    )
                )

        note = await note_repository.find_by_id(conn, note_id, deps.user_id)
    if note:
        outgoing.append(
            NoteGeneratedMessage(
                note_id=note_id,
                topic=note["topic"],
                summary=note["summary"] or "",
            )
        )
    return outgoing


async def _handle_start_learning(msg: StartLearningMessage, deps: Deps) -> SessionContext:
    initial_state: dict[str, Any] = {
        "user_id": deps.user_id,
        "topic": msg.topic,
        "turn_count": 0,
        "should_generate_note": False,
        "session_type": "learning",
        "wrap_up_offered": False,
    }
    if msg.learning_goal and msg.learning_goal.strip():
        initial_state["learning_goal"] = msg.learning_goal.strip()
    if msg.focus_aspects:
        cleaned_aspects = [a.strip() for a in msg.focus_aspects if a and a.strip()]
        if cleaned_aspects:
            initial_state["focus_aspects"] = cleaned_aspects

    return await _start_session(
        session_type="learning",
        deps=deps,
        initial_state=initial_state,
        first_user_content=msg.topic,
    )


async def _handle_start_review(msg: StartReviewMessage, deps: Deps) -> SessionContext | None:
    async with deps.pool.acquire() as conn:
        note = await note_repository.find_by_id(conn, msg.note_id, deps.user_id)
        if not note:
            await deps.websocket.send_text(ErrorMessage(detail="Note not found").model_dump_json())
            return None
        feedbacks = await feedback_repository.find_by_note_id(conn, msg.note_id, deps.user_id)

    initial_state: dict[str, Any] = {
        "user_id": deps.user_id,
        "note_id": msg.note_id,
        "topic": note["topic"],
        "note_content": note["content"],
        "note_summary": note["summary"] or "",
        "turn_count": 0,
        "should_generate_note": False,
        "session_type": "review",
    }
    if feedbacks and feedbacks[-1]["improvements"].strip():
        initial_state["prior_improvements"] = feedbacks[-1]["improvements"]
    return await _start_session(
        session_type="review",
        deps=deps,
        initial_state=initial_state,
        first_user_content=note["topic"],
        note_id=msg.note_id,
    )


async def _rollback_unanswered_turn(session_id: UUID, config: dict[str, Any], deps: Deps) -> str | None:
    """応答が返らないまま残ったユーザーメッセージを state と DB から取り除き、その本文を返す。

    応答生成の途中で切断すると、ユーザーメッセージだけが state と DB に残る。放置すると
    ユーザーは同じ内容を再送するしかなく、履歴に同一発言が二重に残る（実セッションで発生）。
    `turn_count` は対話ノードが走っていないので触らない。
    """
    state = await deps.graph.aget_state(config)
    messages = state.values.get("messages") or []
    if messages and messages[-1].type == "human":
        pending = str(messages[-1].content)
        await deps.graph.aupdate_state(config, {"messages": [RemoveMessage(id=messages[-1].id)]})
        async with deps.pool.acquire() as conn:
            await dialogue_message_repository.delete_last_n(conn, session_id, 1)
        return pending

    # state への反映前に落ちた場合は DB 側にだけ残る
    async with deps.pool.acquire() as conn:
        rows = await dialogue_message_repository.find_by_session_id(conn, session_id)
        if rows and rows[-1]["role"] == "user":
            await dialogue_message_repository.delete_last_n(conn, session_id, 1)
            return str(rows[-1]["content"])
    return None


async def _handle_resume_session(msg: ResumeSessionMessage, deps: Deps) -> SessionContext | None:
    async with deps.pool.acquire() as conn:
        existing = await dialogue_session_repository.find_by_id(conn, msg.session_id, deps.user_id)
    if not existing:
        await deps.websocket.send_text(ErrorMessage(detail="Session not found").model_dump_json())
        return None

    if existing["status"] not in ("in_progress", "disconnect"):
        await deps.websocket.send_text(ErrorMessage(detail="Session is not resumable").model_dump_json())
        return None

    if existing["session_type"] not in ("learning", "review"):
        await deps.websocket.send_text(ErrorMessage(detail="Invalid session type").model_dump_json())
        return None

    if existing["graph_version"] != GRAPH_VERSION:
        async with deps.pool.acquire() as conn:
            await dialogue_session_repository.abandon_by_id(conn, msg.session_id, deps.user_id)
        await deps.websocket.send_text(
            ErrorMessage(detail="このセッションは更新により再開できません。新しく始めてください").model_dump_json()
        )
        return None

    resumed_session_type = cast(Literal["learning", "review"], existing["session_type"])
    config = build_graph_config(session_id=msg.session_id, user_id=deps.user_id, session_type=resumed_session_type)

    async with deps.pool.acquire() as conn:
        if existing["status"] == "disconnect":
            await dialogue_session_repository.update_status(conn, msg.session_id, "in_progress")

    pending = await _rollback_unanswered_turn(msg.session_id, config, deps)

    async with deps.pool.acquire() as conn:
        last_message_order = await dialogue_message_repository.get_max_message_order(conn, msg.session_id)

    progress = await _learning_progress(deps.graph, config) if resumed_session_type == "learning" else None
    await deps.websocket.send_text(
        SessionResumedMessage(
            session_id=msg.session_id,
            session_type=resumed_session_type,
            progress=progress,
        ).model_dump_json()
    )
    if pending is not None:
        await deps.websocket.send_text(PendingMessageRolledBack(content=pending).model_dump_json())

    return SessionContext(
        session_id=msg.session_id,
        config=config,
        session_type=resumed_session_type,
        message_order=last_message_order,
    )


async def _persist_message_images(
    conn: DBConnection,
    message_id: UUID,
    session_id: UUID,
    images: list[ImageAttachment] | None,
) -> list[dict[str, str]]:
    """画像バイナリをストレージへ、参照メタを DB へ保存し、state に載せる参照列を返す。"""
    if not images:
        return []

    storage = get_storage()
    stored: list[tuple[str, str]] = []
    for order, image in enumerate(images):
        ext = _MIME_TO_EXT[image.mime_type]
        storage_key = f"dialogue_images/{session_id}/{message_id}/{order}.{ext}"
        await storage.put(storage_key, base64.b64decode(image.data), image.mime_type)
        stored.append((storage_key, image.mime_type))

    await dialogue_message_image_repository.insert_many(conn, message_id, stored)
    return [{"storage_key": key, "mime_type": mime} for key, mime in stored]


async def _handle_user_message(msg: UserMessage, ctx: SessionContext, deps: Deps) -> SessionContext:
    ctx.message_order += 1
    async with deps.pool.acquire() as conn:
        inserted = await dialogue_message_repository.insert(
            conn, ctx.session_id, "user", msg.content, ctx.message_order, client_message_id=msg.client_message_id
        )
        if inserted is None:
            ctx.message_order -= 1
            return ctx
        attachments = await _persist_message_images(conn, inserted["id"], ctx.session_id, msg.images)

    additional_kwargs: dict[str, Any] = dict(image_attachments_kwargs(attachments))
    if msg.intake_answers is not None:
        additional_kwargs["intake_answers"] = msg.intake_answers.model_dump()
    await deps.graph.aupdate_state(
        ctx.config,
        {"messages": [HumanMessage(content=msg.content, additional_kwargs=additional_kwargs)]},
    )

    try:
        async with traced_graph_run(ctx.config, name="respond-to-user", input=msg.content) as run:
            ai_msg = await _stream_ai_response(
                deps.graph,
                None,
                run.config,
                deps.websocket,
                progress_config=ctx.config if ctx.session_type == "learning" else None,
            )
            run.set_output(ai_msg)

        ctx.message_order += 1
        async with deps.pool.acquire() as conn:
            await dialogue_message_repository.insert(
                conn, ctx.session_id, "assistant", ai_msg, ctx.message_order, client_message_id=None
            )
    except Exception:
        logger.exception("Turn generation failed for session %s", ctx.session_id)
        pending = await _rollback_unanswered_turn(ctx.session_id, ctx.config, deps)
        ctx.message_order -= 1
        await deps.websocket.send_text(ErrorMessage(detail="Internal error").model_dump_json())
        if pending is not None:
            await deps.websocket.send_text(PendingMessageRolledBack(content=pending).model_dump_json())
        return ctx

    state = await deps.graph.aget_state(ctx.config)
    result = state.values

    if not result.get("should_generate_note"):
        return ctx

    if result.get("turn_count", 0) < MIN_TURNS_BEFORE_NOTE:
        await deps.graph.aupdate_state(ctx.config, {"should_generate_note": False})
        return ctx

    ctx.is_session_ended = True
    async with deps.pool.acquire() as conn:
        await dialogue_session_repository.update_status(conn, ctx.session_id, "completed")

    for payload in await _finalize_session(result, ctx, deps):
        await deps.websocket.send_text(payload.model_dump_json())

    await deps.websocket.send_text(SessionEndedMessage().model_dump_json())
    return ctx


async def _handle_cancel_last_message(ctx: SessionContext, deps: Deps) -> SessionContext:
    if ctx.is_session_ended:
        await deps.websocket.send_text(CancelLastMessageError(detail="Session already ended").model_dump_json())
        return ctx

    if ctx.message_order < 4:
        await deps.websocket.send_text(CancelLastMessageError(detail="No cancellable message").model_dump_json())
        return ctx

    state = await deps.graph.aget_state(ctx.config)
    messages_in_state = state.values["messages"]

    last_ai = messages_in_state[-1]
    last_human = messages_in_state[-2]
    if "intake_answers" in last_human.additional_kwargs:
        await deps.websocket.send_text(
            CancelLastMessageError(detail="Intake answers cannot be edited").model_dump_json()
        )
        return ctx

    cancelled_content = str(last_human.content)

    await deps.graph.aupdate_state(
        ctx.config,
        {
            "messages": [
                RemoveMessage(id=last_ai.id),
                RemoveMessage(id=last_human.id),
            ],
            "turn_count": state.values["turn_count"] - 1,
        },
    )

    async with deps.pool.acquire() as conn:
        await dialogue_message_repository.delete_last_n(conn, ctx.session_id, 2)
    ctx.message_order -= 2

    await deps.websocket.send_text(CancelLastMessageSuccess(cancelled_content=cancelled_content).model_dump_json())
    return ctx


async def _handle_end_session(ctx: SessionContext | None, deps: Deps) -> None:
    if ctx is not None:
        ctx.is_session_ended = True
        end_node = "review_dialogue" if ctx.session_type == "review" else "learning_dialogue"
        await deps.graph.aupdate_state(ctx.config, {"should_generate_note": True}, as_node=end_node)
        run_name = "update-review-note" if ctx.session_type == "review" else "generate-learning-note"
        async with deps.pool.acquire() as conn:
            await dialogue_session_repository.update_status(conn, ctx.session_id, "generate_note")
        asyncio.create_task(_generate_note_background(deps.pool, deps.graph, ctx.config, ctx.session_id, run_name))

    await deps.websocket.send_text(SessionEndedMessage(session_id=ctx.session_id if ctx else None).model_dump_json())


router = APIRouter()


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        user_id = await authenticate_websocket(websocket)
    except ValueError:
        return

    deps = Deps(
        pool=await get_pool(),
        graph=websocket.app.state.graph,
        websocket=websocket,
        user_id=user_id,
    )

    ctx: SessionContext | None = None

    try:
        while True:
            user_input = await websocket.receive_text()

            try:
                msg = _incoming_adapter.validate_json(user_input)
            except ValidationError:
                await websocket.send_text(ErrorMessage(detail="Invalid message format").model_dump_json())
                continue

            if isinstance(msg, StartLearningMessage):
                ctx = await _handle_start_learning(msg, deps)
            elif isinstance(msg, StartReviewMessage):
                new_ctx = await _handle_start_review(msg, deps)
                if new_ctx is not None:
                    ctx = new_ctx
            elif isinstance(msg, ResumeSessionMessage):
                new_ctx = await _handle_resume_session(msg, deps)
                if new_ctx is not None:
                    ctx = new_ctx
            elif isinstance(msg, UserMessage):
                if ctx is None:
                    await websocket.send_text(ErrorMessage(detail="Session not started").model_dump_json())
                    continue
                ctx = await _handle_user_message(msg, ctx, deps)
            elif isinstance(msg, CancelLastMessageRequest):
                if ctx is None:
                    await websocket.send_text(CancelLastMessageError(detail="Session not started").model_dump_json())
                    continue
                ctx = await _handle_cancel_last_message(ctx, deps)
            elif isinstance(msg, EndSessionMessage):
                await _handle_end_session(ctx, deps)
                break

    except WebSocketDisconnect:
        if ctx is not None:
            async with deps.pool.acquire() as conn:
                await dialogue_session_repository.update_status(conn, ctx.session_id, "disconnect")
    except Exception:
        logger.exception(
            "WebSocket handler crashed",
            extra={"session_id": str(ctx.session_id) if ctx else None},
        )
        if ctx is not None:
            async with deps.pool.acquire() as conn:
                await dialogue_session_repository.update_status(conn, ctx.session_id, "failed")
        await websocket.send_text(ErrorMessage(detail="Internal error").model_dump_json())
