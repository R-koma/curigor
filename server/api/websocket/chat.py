import asyncio
import base64
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Literal, NamedTuple, cast
from uuid import UUID

import asyncpg
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import AIMessageChunk, HumanMessage, RemoveMessage
from pydantic import TypeAdapter, ValidationError

from api.websocket.auth import authenticate_websocket
from core.database import DBConnection, get_pool
from graph.aspect_map import parse_aspect_map
from graph.coverage import coverage_progress
from graph.depth_map import depth_map_progress
from graph.intake_summary import build_intake_summary
from graph.llm import INTERNAL_LLM_TAG
from graph.multimodal import image_attachments_kwargs
from graph.session_end import has_learner_content
from graph.topic_correction import same_topic
from graph.version import GRAPH_VERSION
from observability.langfuse_tracing import build_graph_config, traced_graph_run
from repositories import (
    collection_synthesis_repository,
    dialogue_message_image_repository,
    dialogue_message_repository,
    dialogue_session_repository,
    feedback_repository,
    note_collection_repository,
    note_repository,
)
from schemas.intake_card import IntakeCard
from schemas.topic_correction import TopicCorrectionCard
from schemas.websocket_message import (
    AssistantMessageChunk,
    AssistantMessageEnd,
    CancelLastMessageError,
    CancelLastMessageRequest,
    CancelLastMessageSuccess,
    EndConfirmation,
    EndSessionMessage,
    ErrorMessage,
    ImageAttachment,
    IncomingMessage,
    IntakeQuestionMessage,
    LearningProgress,
    PendingMessageRolledBack,
    ProgressAspect,
    ResumeSessionMessage,
    SessionEndedMessage,
    SessionResumedMessage,
    SessionStartedMessage,
    SessionType,
    StartLearningMessage,
    StartReviewMessage,
    StartSynthesisMessage,
    TopicCorrectionQuestionMessage,
    TopicEditRejected,
    UserMessage,
    VoiceInputFields,
)
from services.collection_synthesis import build_notes_block, dialogue_connections, label_notes, to_source_notes
from services.review_focus import build_review_focus
from storage import get_storage

logger = logging.getLogger(__name__)

_MIME_TO_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

_STREAMING_NODES = {
    "learning_start",
    "learning_dialogue",
    "review_start",
    "review_dialogue",
    "synthesis_start",
    "synthesis_dialogue",
}

_END_NODES: dict[str, str] = {
    "learning": "learning_dialogue",
    "review": "review_dialogue",
    "synthesis": "synthesis_dialogue",
}
_END_RUN_NAMES: dict[str, str] = {
    "learning": "generate-learning-note",
    "review": "update-review-note",
    "synthesis": "finish-synthesis",
}

_incoming_adapter: TypeAdapter[IncomingMessage] = TypeAdapter(IncomingMessage)


@dataclass
class SessionContext:
    session_id: UUID
    config: dict[str, Any]
    session_type: SessionType
    message_order: int
    is_session_ended: bool = False
    topic: str | None = None


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


class StreamedTurn(NamedTuple):
    content: str
    question: IntakeQuestionMessage | None
    topic: str | None
    topic_correction: TopicCorrectionQuestionMessage | None = None
    end_confirmation_status: str | None = None


async def _read_turn_state(graph: Any, config: dict[str, Any]) -> dict[str, Any] | None:
    """進捗とカードは表示専用の副次情報。取得に失敗してもターンの成否に影響させず `None` を返す。"""
    try:
        return cast(dict[str, Any], (await graph.aget_state(config)).values)
    except Exception:
        logger.exception("Failed to read turn state")
        return None


def _progress_aspects(depth_map: dict[str, Any], covered: list[dict[str, Any]]) -> list[ProgressAspect]:
    stages = {c["aspect_id"]: c["reached_stage"] for c in covered}
    ordered = sorted(depth_map["aspects"], key=lambda a: not a["is_core"])
    return [ProgressAspect(name=a["name"], is_core=a["is_core"], reached_stage=stages.get(a["id"])) for a in ordered]


def _progress_from_values(values: dict[str, Any]) -> LearningProgress | None:
    if values.get("intake_complete") is False:
        return None
    depth_map = values.get("depth_map")
    covered = values.get("map_covered") or []
    if depth_map:
        progress = depth_map_progress(covered, depth_map)
        aspects = _progress_aspects(depth_map, covered)
    else:
        progress = coverage_progress(values.get("covered_aspects") or [], values.get("focus_aspects"))
        aspects = []
    return LearningProgress(
        reached_aspects=list(progress.reached_aspects),
        target_count=progress.target_count,
        is_complete=progress.is_complete,
        aspects=aspects,
        intake=build_intake_summary(values),
    )


def _intake_question_from_values(values: dict[str, Any]) -> IntakeQuestionMessage | None:
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


def _topic_correction_question_from_values(values: dict[str, Any]) -> TopicCorrectionQuestionMessage | None:
    messages = values.get("messages") or []
    if not messages or messages[-1].type != "ai":
        return None
    card = messages[-1].additional_kwargs.get("topic_correction_card")
    if card is None:
        return None
    return TopicCorrectionQuestionMessage(
        content=str(messages[-1].content), card=TopicCorrectionCard.model_validate(card)
    )


def _trial_kickoff_from_values(values: dict[str, Any]) -> str | None:
    messages = values.get("messages") or []
    if not messages or messages[-1].type != "ai" or not messages[-1].additional_kwargs.get("trial_kickoff"):
        return None
    return str(messages[-1].content)


def _end_confirmation_from_values(values: dict[str, Any]) -> EndConfirmation | None:
    if values.get("end_confirmation") != "offered":
        return None
    return EndConfirmation(creates_note=has_learner_content(values))


async def _stream_ai_response(
    graph: Any,
    input: Any,
    config: dict[str, Any],
    websocket: WebSocket,
    *,
    state_config: dict[str, Any] | None = None,
    with_progress: bool = False,
) -> StreamedTurn:
    ai_content = ""
    async for msg, metadata in graph.astream(input, config, stream_mode="messages"):
        node = metadata.get("langgraph_node", "")
        if INTERNAL_LLM_TAG in (metadata.get("tags") or []):
            continue
        if isinstance(msg, AIMessageChunk) and node in _STREAMING_NODES and msg.content:
            chunk = str(msg.content)
            ai_content += chunk
            await websocket.send_text(AssistantMessageChunk(content=chunk).model_dump_json())
    values = await _read_turn_state(graph, state_config) if state_config is not None else None
    question = _intake_question_from_values(values) if values is not None else None
    if question is not None:
        await websocket.send_text(question.model_dump_json())
        ai_content = ai_content or question.content
    correction = _topic_correction_question_from_values(values) if values is not None else None
    if correction is not None:
        await websocket.send_text(correction.model_dump_json())
        ai_content = ai_content or correction.content
    kickoff = _trial_kickoff_from_values(values) if values is not None and not ai_content else None
    if kickoff:
        await websocket.send_text(AssistantMessageChunk(content=kickoff).model_dump_json())
        ai_content = kickoff
    progress = _progress_from_values(values) if values is not None and with_progress else None
    topic = (str(values.get("topic") or "") or None) if values is not None else None
    end_confirmation = _end_confirmation_from_values(values) if values is not None else None
    await websocket.send_text(
        AssistantMessageEnd(progress=progress, topic=topic, end_confirmation=end_confirmation).model_dump_json()
    )
    status = values.get("end_confirmation") if values is not None else None
    return StreamedTurn(ai_content, question, topic, correction, status)


def _input_mode(voice: VoiceInputFields | None) -> str:
    if voice is None or not voice.raw_transcript:
        return "text"
    return "voice_auto" if voice.auto_sent else "voice"


async def _start_session(
    *,
    session_type: SessionType,
    deps: Deps,
    initial_state: dict[str, Any],
    first_user_content: str,
    note_id: UUID | None = None,
    collection_id: UUID | None = None,
    session_topic: str | None = None,
    first_user_voice: VoiceInputFields | None = None,
    trial: bool = False,
) -> SessionContext:
    """セッション作成・SessionStarted 送信・初期 user/assistant メッセージ保存までを共通化。"""
    session_id = uuid.uuid4()
    config = build_graph_config(session_id=session_id, user_id=deps.user_id, session_type=session_type, trial=trial)

    message_order = 1
    async with deps.pool.acquire() as conn:
        if session_type != "synthesis":
            await dialogue_session_repository.abandon_active_by_user(conn, deps.user_id)
        await dialogue_session_repository.create(
            conn=conn,
            session_id=session_id,
            user_id=deps.user_id,
            session_type=session_type,
            graph_version=GRAPH_VERSION,
            note_id=note_id,
            collection_id=collection_id,
            topic=session_topic,
            is_trial=trial,
        )
        await dialogue_message_repository.insert(
            conn,
            session_id,
            "user",
            first_user_content,
            message_order,
            client_message_id=None,
            input_mode=_input_mode(first_user_voice),
            raw_transcript=first_user_voice.raw_transcript if first_user_voice else None,
            stt_method=first_user_voice.stt_method if first_user_voice else None,
            stt_latency_ms=first_user_voice.stt_latency_ms if first_user_voice else None,
        )

    await deps.websocket.send_text(
        SessionStartedMessage(session_id=session_id, session_type=session_type).model_dump_json()
    )

    initial_state["dialogue_session_id"] = str(session_id)

    async with traced_graph_run(config, name=f"start-{session_type}-session", input=first_user_content) as run:
        turn = await _stream_ai_response(
            deps.graph,
            initial_state,
            run.config,
            deps.websocket,
            state_config=config,
            with_progress=session_type == "learning",
        )
        run.set_output(turn.content)

    question = turn.question

    message_order += 1
    async with deps.pool.acquire() as conn:
        await dialogue_message_repository.insert(
            conn,
            session_id,
            "assistant",
            turn.content,
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
        topic=question.topic if question else None,
    )


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
    if msg.trial:
        initial_state["trial"] = True

    return await _start_session(
        session_type="learning",
        deps=deps,
        initial_state=initial_state,
        first_user_content=msg.topic,
        session_topic=msg.topic if msg.trial else None,
        first_user_voice=msg,
        trial=msg.trial,
    )


async def _handle_start_review(msg: StartReviewMessage, deps: Deps) -> SessionContext | None:
    async with deps.pool.acquire() as conn:
        note = await note_repository.find_by_id(conn, msg.note_id, deps.user_id)
        if not note:
            await deps.websocket.send_text(ErrorMessage(detail="ノートが見つかりません").model_dump_json())
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
    focus = build_review_focus(
        feedbacks[-1] if feedbacks else None, parse_aspect_map(note["aspect_map"]), msg.focus_aspect_ids
    )
    if focus.prior_improvements:
        initial_state["prior_improvements"] = focus.prior_improvements
    if focus.focus_aspects:
        initial_state["review_focus_aspects"] = focus.focus_aspects
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
    聞き取りカード・トピック訂正の確認への回答と、ヘッダーでのトピックの編集は、本文（整形済みの文字列）を入力欄へ戻しても構造化された
    回答を再現できないため、空文字を返す（カードが再び最後のメッセージになり、そこから答え直す）。
    """
    state = await deps.graph.aget_state(config)
    messages = state.values.get("messages") or []
    if messages and messages[-1].type == "human":
        kwargs = messages[-1].additional_kwargs
        answers_a_card = "intake_answers" in kwargs or "topic_correction_answer" in kwargs or "topic_edit" in kwargs
        pending = "" if answers_a_card else str(messages[-1].content)
        await deps.graph.aupdate_state(config, {"messages": [RemoveMessage(id=messages[-1].id)]})
        async with deps.pool.acquire() as conn:
            await dialogue_message_repository.delete_last_n(conn, session_id, 1)
        return pending

    # state への反映前に落ちた場合は DB 側にだけ残る
    async with deps.pool.acquire() as conn:
        rows = await dialogue_message_repository.find_by_session_id(conn, session_id)
        if rows and rows[-1]["role"] == "user":
            await dialogue_message_repository.delete_last_n(conn, session_id, 1)
            answers_card = rows[-1]["topic_edit"] is not None or (
                len(rows) >= 2
                and (rows[-2]["intake_card"] is not None or rows[-2]["topic_correction_card"] is not None)
            )
            return "" if answers_card else str(rows[-1]["content"])
    return None


async def _handle_start_synthesis(msg: StartSynthesisMessage, deps: Deps) -> SessionContext | None:
    async with deps.pool.acquire() as conn:
        collection = await note_collection_repository.find_by_id(conn, msg.collection_id, deps.user_id)
        if collection is None:
            await deps.websocket.send_text(ErrorMessage(detail="まとめノートが見つかりません").model_dump_json())
            return None
        synthesis = await collection_synthesis_repository.find_by_collection_id(conn, msg.collection_id, deps.user_id)
        rows = await note_repository.find_contents_by_collection_id(conn, msg.collection_id, deps.user_id)

    connections = dialogue_connections(synthesis["connections"]) if synthesis else []
    if not connections:
        await deps.websocket.send_text(ErrorMessage(detail="まとめの対象になるつながりがありません").model_dump_json())
        return None

    initial_state: dict[str, Any] = {
        "user_id": deps.user_id,
        "topic": collection["name"],
        "turn_count": 0,
        "should_generate_note": False,
        "session_type": "synthesis",
        "collection_id": msg.collection_id,
        "synthesis_notes": build_notes_block(label_notes(to_source_notes(rows))),
        "synthesis_connections": connections,
    }
    return await _start_session(
        session_type="synthesis",
        deps=deps,
        initial_state=initial_state,
        first_user_content=collection["name"],
        collection_id=msg.collection_id,
        session_topic=collection["name"],
    )


async def _handle_resume_session(msg: ResumeSessionMessage, deps: Deps) -> SessionContext | None:
    async with deps.pool.acquire() as conn:
        existing = await dialogue_session_repository.find_by_id(conn, msg.session_id, deps.user_id)
    if not existing:
        await deps.websocket.send_text(
            ErrorMessage(detail="セッションが見つかりません。新しく始めてください").model_dump_json()
        )
        return None

    if existing["status"] not in ("in_progress", "disconnect"):
        await deps.websocket.send_text(
            ErrorMessage(detail="このセッションは再開できません。新しく始めてください").model_dump_json()
        )
        return None

    if existing["session_type"] not in ("learning", "review"):
        await deps.websocket.send_text(
            ErrorMessage(detail="セッションの種類が正しくありません。新しく始めてください").model_dump_json()
        )
        return None

    if existing["graph_version"] != GRAPH_VERSION:
        async with deps.pool.acquire() as conn:
            await dialogue_session_repository.abandon_by_id(conn, msg.session_id, deps.user_id)
        await deps.websocket.send_text(
            ErrorMessage(detail="このセッションは更新により再開できません。新しく始めてください").model_dump_json()
        )
        return None

    resumed_session_type = cast(Literal["learning", "review"], existing["session_type"])
    config = build_graph_config(
        session_id=msg.session_id,
        user_id=deps.user_id,
        session_type=resumed_session_type,
        trial=bool(existing.get("is_trial")),
    )

    async with deps.pool.acquire() as conn:
        if existing["status"] == "disconnect":
            await dialogue_session_repository.update_status(conn, msg.session_id, "in_progress")

    pending = await _rollback_unanswered_turn(msg.session_id, config, deps)

    async with deps.pool.acquire() as conn:
        last_message_order = await dialogue_message_repository.get_max_message_order(conn, msg.session_id)

    values = await _read_turn_state(deps.graph, config)
    progress = _progress_from_values(values) if values is not None and resumed_session_type == "learning" else None
    end_confirmation = _end_confirmation_from_values(values) if values is not None else None
    await deps.websocket.send_text(
        SessionResumedMessage(
            session_id=msg.session_id,
            session_type=resumed_session_type,
            progress=progress,
            end_confirmation=end_confirmation,
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


async def _pending_topic_correction_answer(msg: UserMessage, ctx: SessionContext, deps: Deps) -> str | None:
    if msg.topic_correction_answer is None:
        return None
    state = await deps.graph.aget_state(ctx.config)
    return msg.topic_correction_answer if state.values.get("pending_topic_correction") else None


async def _topic_edit_rejection(topic: str, ctx: SessionContext, deps: Deps) -> str | None:
    if ctx.session_type != "learning":
        return "このセッションではトピックを変更できません"
    values = (await deps.graph.aget_state(ctx.config)).values
    if not values.get("intake_complete") or not values.get("depth_map"):
        return "学習の前提を答えた後にトピックを変更できます"
    if same_topic(topic, str(values.get("topic") or "")):
        return "今と同じトピックです"
    return None


async def _handle_user_message(msg: UserMessage, ctx: SessionContext, deps: Deps) -> SessionContext:
    if msg.topic_edit is not None:
        rejection = await _topic_edit_rejection(msg.topic_edit, ctx, deps)
        if rejection is not None:
            await deps.websocket.send_text(TopicEditRejected(detail=rejection).model_dump_json())
            return ctx
    topic_correction_answer = await _pending_topic_correction_answer(msg, ctx, deps)
    ctx.message_order += 1
    async with deps.pool.acquire() as conn:
        inserted = await dialogue_message_repository.insert(
            conn,
            ctx.session_id,
            "user",
            msg.content,
            ctx.message_order,
            client_message_id=msg.client_message_id,
            input_mode=_input_mode(msg),
            raw_transcript=msg.raw_transcript,
            intake_answers=msg.intake_answers.model_dump_json() if msg.intake_answers is not None else None,
            topic_correction_answer=topic_correction_answer,
            topic_edit=msg.topic_edit,
            stt_method=msg.stt_method,
            stt_latency_ms=msg.stt_latency_ms,
        )
        if inserted is None:
            ctx.message_order -= 1
            return ctx
        attachments = await _persist_message_images(conn, inserted["id"], ctx.session_id, msg.images)

    additional_kwargs: dict[str, Any] = dict(image_attachments_kwargs(attachments))
    if msg.intake_answers is not None:
        additional_kwargs["intake_answers"] = msg.intake_answers.model_dump()
    if topic_correction_answer is not None:
        additional_kwargs["topic_correction_answer"] = topic_correction_answer
    if msg.topic_edit is not None:
        additional_kwargs["topic_edit"] = msg.topic_edit
    await deps.graph.aupdate_state(
        ctx.config,
        {"messages": [HumanMessage(content=msg.content, additional_kwargs=additional_kwargs)]},
    )

    try:
        async with traced_graph_run(ctx.config, name="respond-to-user", input=msg.content) as run:
            turn = await _stream_ai_response(
                deps.graph,
                None,
                run.config,
                deps.websocket,
                state_config=ctx.config,
                with_progress=ctx.session_type == "learning",
            )
            run.set_output(turn.content)

        async with deps.pool.acquire() as conn:
            if turn.end_confirmation_status != "confirmed":
                ctx.message_order += 1
                await dialogue_message_repository.insert(
                    conn,
                    ctx.session_id,
                    "assistant",
                    turn.content,
                    ctx.message_order,
                    client_message_id=None,
                    topic_correction_card=(
                        turn.topic_correction.card.model_dump_json() if turn.topic_correction else None
                    ),
                )
            if turn.topic and turn.topic != ctx.topic:
                await dialogue_session_repository.update_topic(conn, ctx.session_id, turn.topic)
                ctx.topic = turn.topic
    except Exception:
        logger.exception("Turn generation failed for session %s", ctx.session_id)
        pending = await _rollback_unanswered_turn(ctx.session_id, ctx.config, deps)
        ctx.message_order -= 1
        await deps.websocket.send_text(
            ErrorMessage(detail="問題が発生しました。時間をおいてもう一度お試しください").model_dump_json()
        )
        if pending is not None:
            await deps.websocket.send_text(PendingMessageRolledBack(content=pending).model_dump_json())
        return ctx

    if turn.end_confirmation_status == "confirmed":
        await _handle_end_session(ctx, deps)
    return ctx


async def _handle_cancel_last_message(ctx: SessionContext, deps: Deps) -> SessionContext:
    if ctx.message_order < 4:
        await deps.websocket.send_text(CancelLastMessageError(detail="取り消せる発言がありません").model_dump_json())
        return ctx

    state = await deps.graph.aget_state(ctx.config)
    messages_in_state = state.values["messages"]

    last_ai = messages_in_state[-1]
    last_human = messages_in_state[-2]
    answers_intake_card = len(messages_in_state) >= 3 and "intake_card" in messages_in_state[-3].additional_kwargs
    answers_topic_correction_card = (
        len(messages_in_state) >= 3 and "topic_correction_card" in messages_in_state[-3].additional_kwargs
    )
    if "topic_edit" in last_human.additional_kwargs:
        await deps.websocket.send_text(
            CancelLastMessageError(detail="トピックの変更は取り消せません").model_dump_json()
        )
        return ctx
    if "topic_correction_answer" in last_human.additional_kwargs or answers_topic_correction_card:
        await deps.websocket.send_text(
            CancelLastMessageError(detail="トピックの変更への回答は取り消せません").model_dump_json()
        )
        return ctx
    if "intake_answers" in last_human.additional_kwargs or answers_intake_card:
        await deps.websocket.send_text(
            CancelLastMessageError(detail="聞き取りへの回答は取り消せません").model_dump_json()
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
            "pending_topic_correction": None,
            "end_confirmation": None,
        },
    )

    async with deps.pool.acquire() as conn:
        await dialogue_message_repository.delete_last_n(conn, ctx.session_id, 2)
    ctx.message_order -= 2

    await deps.websocket.send_text(CancelLastMessageSuccess(cancelled_content=cancelled_content).model_dump_json())
    return ctx


async def _handle_end_session(ctx: SessionContext | None, deps: Deps) -> None:
    if ctx is None:
        await deps.websocket.send_text(SessionEndedMessage().model_dump_json())
        return
    ctx.is_session_ended = True
    values = (await deps.graph.aget_state(ctx.config)).values
    if not has_learner_content(values):
        async with deps.pool.acquire() as conn:
            await dialogue_session_repository.update_status(conn, ctx.session_id, "completed")
        await deps.websocket.send_text(SessionEndedMessage(note_skipped=True).model_dump_json())
        return
    end_node = _END_NODES[ctx.session_type]
    await deps.graph.aupdate_state(ctx.config, {"should_generate_note": True}, as_node=end_node)
    run_name = _END_RUN_NAMES[ctx.session_type]
    async with deps.pool.acquire() as conn:
        await dialogue_session_repository.update_status(conn, ctx.session_id, "generate_note")
    asyncio.create_task(_generate_note_background(deps.pool, deps.graph, ctx.config, ctx.session_id, run_name))
    await deps.websocket.send_text(SessionEndedMessage(session_id=ctx.session_id).model_dump_json())


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
                await websocket.send_text(
                    ErrorMessage(
                        detail="メッセージを処理できませんでした。ページを再読み込みしてください"
                    ).model_dump_json()
                )
                continue

            if isinstance(msg, StartLearningMessage):
                ctx = await _handle_start_learning(msg, deps)
            elif isinstance(msg, StartSynthesisMessage):
                new_ctx = await _handle_start_synthesis(msg, deps)
                if new_ctx is not None:
                    ctx = new_ctx
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
                    await websocket.send_text(
                        ErrorMessage(
                            detail="セッションが開始されていません。ページを再読み込みしてください"
                        ).model_dump_json()
                    )
                    continue
                ctx = await _handle_user_message(msg, ctx, deps)
                if ctx.is_session_ended:
                    break
            elif isinstance(msg, CancelLastMessageRequest):
                if ctx is None:
                    await websocket.send_text(
                        CancelLastMessageError(
                            detail="セッションが開始されていません。ページを再読み込みしてください"
                        ).model_dump_json()
                    )
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
        await websocket.send_text(
            ErrorMessage(detail="問題が発生しました。時間をおいてもう一度お試しください").model_dump_json()
        )
