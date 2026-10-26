import asyncio
import base64
import contextlib
import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Literal, NamedTuple, cast
from uuid import UUID

import asyncpg
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import AIMessageChunk, BaseMessage, HumanMessage, RemoveMessage
from pydantic import TypeAdapter, ValidationError

from api.websocket.auth import authenticate_websocket
from core import config as app_config
from core.database import DBConnection, get_pool
from core.terms import TERMS_VERSION
from graph.aspect_map import parse_aspect_map
from graph.coverage import coverage_progress
from graph.depth_map import depth_map_progress
from graph.intake_summary import build_intake_summary
from graph.llm import INTERNAL_LLM_TAG
from graph.memo_handoff import memo_terms_from_glossary
from graph.multimodal import image_attachments_kwargs
from graph.review_plan import ReviewPlanPoint, order_review_points
from graph.review_progress import initial_review_points
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
    llm_usage_repository,
    note_collection_repository,
    note_repository,
    review_plan_repository,
    study_memo_repository,
    user_consent_repository,
)
from schemas.intake_card import IntakeCard
from schemas.topic_correction import TopicCorrectionCard
from schemas.websocket_message import (
    MAX_MESSAGE_CONTENT_LENGTH,
    PROTOCOL_VERSION,
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
    SessionTakenOver,
    SessionType,
    StartExploreMessage,
    StartLearningMessage,
    StartReviewMessage,
    StartSynthesisMessage,
    TopicCorrectionQuestionMessage,
    TopicEditRejected,
    UserMessage,
    VoiceInputFields,
)
from services.collection_synthesis import build_notes_block, dialogue_connections, label_notes, to_source_notes
from services.explore_gap import gap_opening_utterance, resolve_gap
from services.review_focus import build_review_focus
from services.review_plan import generate_review_plan
from services.transcription_keywords import keyword_source, schedule_transcription_keywords
from storage import dialogue_image_prefix, get_storage

logger = logging.getLogger(__name__)

_MIME_TO_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

_STREAMING_NODES = {
    "learning_start",
    "learning_dialogue",
    "review_start",
    "review_dialogue",
    "synthesis_start",
    "synthesis_dialogue",
    "explore_start",
    "explore_dialogue",
}

_END_NODES: dict[str, str] = {
    "learning": "learning_dialogue",
    "review": "review_dialogue",
    "synthesis": "synthesis_dialogue",
    "explore": "explore_dialogue",
}
_END_RUN_NAMES: dict[str, str] = {
    "learning": "generate-learning-note",
    "review": "update-review-note",
    "synthesis": "finish-synthesis",
    "explore": "generate-study-memo",
}

TURN_OWNERSHIP_POLL_SECONDS = 1.0
TURN_SETTLE_POLL_SECONDS = 0.2
TURN_SETTLE_TIMEOUT_SECONDS = 10.0
TURN_STALE_AFTER = timedelta(minutes=3)

_TAKEN_OVER_DETAIL = "このセッションは別の画面で開かれたか終了したため、この画面では続けられません"
_NOTHING_TO_CANCEL_DETAIL = "取り消せる発言がありません"

_incoming_adapter: TypeAdapter[IncomingMessage] = TypeAdapter(IncomingMessage)
# asyncio はタスクを弱参照でしか持たないため、完了まで参照を保持する
_background_plans: set[asyncio.Task[list[ReviewPlanPoint] | None]] = set()

_MESSAGE_BODY_FIELDS = {"content", "raw_transcript"}


def _validation_error_detail(error: ValidationError) -> str:
    if any(e["type"] == "string_too_long" and e["loc"][-1] in _MESSAGE_BODY_FIELDS for e in error.errors()):
        return f"発言が長すぎます。{MAX_MESSAGE_CONTENT_LENGTH:,}字以内にしてください"
    return "メッセージを処理できませんでした。ページを再読み込みしてください"


@dataclass
class SessionContext:
    session_id: UUID
    config: dict[str, Any]
    session_type: SessionType
    message_order: int
    is_session_ended: bool = False
    is_taken_over: bool = False
    topic: str | None = None


class Inbox:
    def __init__(self, websocket: WebSocket) -> None:
        self._websocket = websocket
        self._receiving: asyncio.Task[str] | None = None
        self._returned: list[str] = []

    def receiving(self) -> asyncio.Task[str]:
        if self._receiving is None:
            self._receiving = asyncio.create_task(self._websocket.receive_text())
        return self._receiving

    def take(self) -> str:
        task = self.receiving()
        self._receiving = None
        return task.result()

    def push_front(self, text: str) -> None:
        self._returned.insert(0, text)

    def take_ready_if(self, accept: Callable[[str], bool]) -> str | None:
        if self._returned:
            return self._returned.pop(0) if accept(self._returned[0]) else None
        task = self._receiving
        if task is None or not task.done() or task.exception() is not None or not accept(task.result()):
            return None
        return self.take()

    async def next(self) -> str:
        if self._returned:
            return self._returned.pop(0)
        await asyncio.wait({self.receiving()})
        return self.take()

    def close(self) -> None:
        if self._receiving is not None:
            self._receiving.cancel()
            self._receiving = None


@dataclass
class Deps:
    pool: asyncpg.Pool
    graph: Any
    websocket: WebSocket
    user_id: str
    connection_id: UUID
    inbox: Inbox


_DAILY_LIMIT_DETAILS: dict[str, tuple[Literal["daily_session_limit_reached", "daily_turn_limit_reached"], str]] = {
    "session_start": (
        "daily_session_limit_reached",
        "今日始められるセッションの上限（{limit} 回）に達しました。"
        "日付が変わると（日本時間の 0 時）、また始められます",
    ),
    "turn": (
        "daily_turn_limit_reached",
        "今日の発言の上限（{limit} 回）に達しました。日付が変わると（日本時間の 0 時）、また送れます",
    ),
}


async def _reserve_llm_usage(operation: Literal["session_start", "turn"], deps: Deps) -> UUID | None:
    limit = app_config.DAILY_SESSION_START_LIMIT if operation == "session_start" else app_config.DAILY_TURN_LIMIT
    async with deps.pool.acquire() as conn:
        usage_id = await llm_usage_repository.reserve(conn, deps.user_id, operation, app_config.REVIEW_TIMEZONE, limit)
    if usage_id is None:
        code, detail = _DAILY_LIMIT_DETAILS[operation]
        await deps.websocket.send_text(ErrorMessage(code=code, detail=detail.format(limit=limit)).model_dump_json())
    return usage_id


async def _cancel_llm_usage(usage_id: UUID, deps: Deps) -> None:
    async with deps.pool.acquire() as conn:
        await llm_usage_repository.cancel(conn, usage_id)


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


_UNSTREAMED_TEXT_KEYS = ("trial_kickoff", "memo_kickoff")


def _unstreamed_text_from_values(values: dict[str, Any]) -> str | None:
    messages = values.get("messages") or []
    if not messages or messages[-1].type != "ai":
        return None
    kwargs = messages[-1].additional_kwargs
    if not any(kwargs.get(key) for key in _UNSTREAMED_TEXT_KEYS):
        return None
    return str(messages[-1].content)


def _end_confirmation_from_values(values: dict[str, Any]) -> EndConfirmation | None:
    if values.get("end_confirmation") != "offered":
        return None
    return EndConfirmation(creates_note=has_learner_content(values))


def _note_peek_available_from_values(values: dict[str, Any]) -> bool:
    if values.get("end_confirmation") == "offered":
        return False
    current_id = values.get("review_current_point_id")
    current = next((p for p in values.get("review_points") or [] if p["id"] == current_id), None)
    return current is not None and current["status"] == "hinted"


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
        if isinstance(msg, AIMessageChunk) and node in _STREAMING_NODES and (chunk := msg.text):
            ai_content += chunk
            await websocket.send_text(AssistantMessageChunk(content=chunk).model_dump_json())
    values = await _read_turn_state(graph, state_config) if state_config is not None else None
    if values is not None:
        _schedule_keywords(values)
    question = _intake_question_from_values(values) if values is not None else None
    if question is not None:
        await websocket.send_text(question.model_dump_json())
        ai_content = ai_content or question.content
    correction = _topic_correction_question_from_values(values) if values is not None else None
    if correction is not None:
        await websocket.send_text(correction.model_dump_json())
        ai_content = ai_content or correction.content
    kickoff = _unstreamed_text_from_values(values) if values is not None and not ai_content else None
    if kickoff:
        await websocket.send_text(AssistantMessageChunk(content=kickoff).model_dump_json())
        ai_content = kickoff
    progress = _progress_from_values(values) if values is not None and with_progress else None
    topic = (str(values.get("topic") or "") or None) if values is not None else None
    end_confirmation = _end_confirmation_from_values(values) if values is not None else None
    await websocket.send_text(
        AssistantMessageEnd(
            progress=progress,
            topic=topic,
            end_confirmation=end_confirmation,
            note_peek_available=values is not None and _note_peek_available_from_values(values),
        ).model_dump_json()
    )
    status = values.get("end_confirmation") if values is not None else None
    return StreamedTurn(ai_content, question, topic, correction, status)


def _schedule_keywords(values: dict[str, Any]) -> None:
    source = keyword_source(values)
    session_id = values.get("dialogue_session_id")
    user_id = values.get("user_id")
    if source is not None and session_id and user_id:
        schedule_transcription_keywords(UUID(str(session_id)), str(user_id), source)


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
    announce_first_message: bool = False,
    first_user_voice: VoiceInputFields | None = None,
    trial: bool = False,
    study_memo_id: UUID | None = None,
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
            study_memo_id=study_memo_id,
            connection_id=deps.connection_id,
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
        SessionStartedMessage(
            session_id=session_id,
            session_type=session_type,
            topic=session_topic if announce_first_message else None,
            first_message=first_user_content if announce_first_message else None,
        ).model_dump_json(exclude_none=True)
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
    started_topic = turn.topic if session_type == "explore" else None
    saved_topic = question.topic if question is not None else started_topic

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
        if saved_topic:
            await dialogue_session_repository.update_topic(conn, session_id, saved_topic)

    return SessionContext(
        session_id=session_id,
        config=config,
        session_type=session_type,
        message_order=message_order,
        topic=saved_topic,
    )


async def _handle_start_explore(msg: StartExploreMessage, deps: Deps) -> SessionContext | None:
    initial_state: dict[str, Any] = {
        "user_id": deps.user_id,
        "topic": msg.topic,
        "turn_count": 0,
        "should_generate_note": False,
        "session_type": "explore",
        "wrap_up_offered": False,
    }
    first_user_content = msg.topic
    session_topic: str | None = None
    if msg.source is not None:
        async with deps.pool.acquire() as conn:
            note = await note_repository.find_by_id(conn, msg.source.note_id, deps.user_id)
            feedbacks = (
                await feedback_repository.find_by_note_id(conn, msg.source.note_id, deps.user_id) if note else []
            )
        if note is None:
            await deps.websocket.send_text(
                ErrorMessage(code="note_not_found", detail="ノートが見つかりません").model_dump_json()
            )
            return None
        gap = resolve_gap(note, feedbacks, msg.source)
        if gap is None:
            await deps.websocket.send_text(
                ErrorMessage(
                    code="improvement_not_found", detail="この改善点は新しいフィードバックで置き換わりました"
                ).model_dump_json()
            )
            return None
        initial_state["topic"] = note["topic"]
        initial_state["explore_gap"] = gap
        first_user_content = gap_opening_utterance(gap)
        session_topic = note["topic"]
    return await _start_session(
        session_type="explore",
        deps=deps,
        initial_state=initial_state,
        first_user_content=first_user_content,
        first_user_voice=msg,
        session_topic=session_topic,
        announce_first_message=msg.source is not None,
    )


async def _find_study_memo(memo_id: UUID | None, deps: Deps) -> dict[str, Any] | None:
    if memo_id is None:
        return None
    async with deps.pool.acquire() as conn:
        return await study_memo_repository.find_by_id(conn, memo_id, deps.user_id)


async def _handle_start_learning(msg: StartLearningMessage, deps: Deps) -> SessionContext:
    memo = await _find_study_memo(msg.study_memo_id, deps)
    topic = str(memo["topic"]) if memo is not None else msg.topic
    initial_state: dict[str, Any] = {
        "user_id": deps.user_id,
        "topic": topic,
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
    trial = msg.trial and memo is None
    if trial:
        initial_state["trial"] = True
    if memo is not None:
        initial_state["study_memo_id"] = str(memo["id"])
        initial_state["memo_terms"] = memo_terms_from_glossary(memo["glossary"])
        if memo["depth_map"].get("aspects"):
            initial_state["memo_depth_map"] = memo["depth_map"]
        if memo["source"]:
            initial_state["learning_source"] = memo["source"]

    return await _start_session(
        session_type="learning",
        deps=deps,
        initial_state=initial_state,
        first_user_content=topic,
        session_topic=topic if trial or memo is not None else None,
        first_user_voice=msg,
        trial=trial,
        study_memo_id=memo["id"] if memo is not None else None,
    )


async def _handle_start_review(msg: StartReviewMessage, deps: Deps) -> SessionContext | None:
    async with deps.pool.acquire() as conn:
        note = await note_repository.find_by_id(conn, msg.note_id, deps.user_id)
        if not note:
            await deps.websocket.send_text(
                ErrorMessage(code="note_not_found", detail="ノートが見つかりません").model_dump_json()
            )
            return None
        feedbacks = await feedback_repository.find_by_note_id(conn, msg.note_id, deps.user_id)
        saved_plan = await review_plan_repository.find_by_note_id(conn, msg.note_id, deps.user_id)
        memo_aspect_ids = (
            await study_memo_repository.find_priority_aspect_ids(conn, feedbacks[-1]["id"], deps.user_id)
            if feedbacks
            else []
        )

    plan_points: list[ReviewPlanPoint] | None = saved_plan["points"] if saved_plan else None
    if saved_plan is None:
        plan_points = await _generate_plan_within_timeout(msg.note_id, deps.user_id)

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
    if plan_points:
        initial_state["review_points"] = initial_review_points(order_review_points(plan_points, memo_aspect_ids))
        initial_state["review_current_point_id"] = None
        initial_state["wrap_up_offered"] = False
    else:
        focus = build_review_focus(
            feedbacks[-1] if feedbacks else None,
            parse_aspect_map(note["aspect_map"]),
            memo_aspect_ids,
        )
        if focus.prior_improvements:
            initial_state["prior_improvements"] = focus.prior_improvements
        if focus.priority_aspects:
            initial_state["review_priority_aspects"] = focus.priority_aspects
    return await _start_session(
        session_type="review",
        deps=deps,
        initial_state=initial_state,
        first_user_content=note["topic"],
        note_id=msg.note_id,
    )


async def _generate_plan_within_timeout(note_id: UUID, user_id: str) -> list[ReviewPlanPoint] | None:
    def forget(task: asyncio.Task[list[ReviewPlanPoint] | None]) -> None:
        _background_plans.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.warning("review plan generation at start failed for note %s", note_id, exc_info=task.exception())

    task = asyncio.create_task(generate_review_plan(note_id, user_id))
    _background_plans.add(task)
    task.add_done_callback(forget)
    try:
        return await asyncio.wait_for(asyncio.shield(task), app_config.REVIEW_PLAN_SYNC_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.info("review plan generation for note %s continues in the background", note_id)
        return None
    except Exception:
        return None


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
            await deps.websocket.send_text(
                ErrorMessage(code="collection_not_found", detail="まとめノートが見つかりません").model_dump_json()
            )
            return None
        synthesis = await collection_synthesis_repository.find_by_collection_id(conn, msg.collection_id, deps.user_id)
        rows = await note_repository.find_contents_by_collection_id(conn, msg.collection_id, deps.user_id)

    connections = dialogue_connections(synthesis["connections"]) if synthesis else []
    if not connections:
        await deps.websocket.send_text(
            ErrorMessage(
                code="no_synthesis_connections", detail="まとめの対象になるつながりがありません"
            ).model_dump_json()
        )
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
            ErrorMessage(
                code="session_not_found", detail="セッションが見つかりません。新しく始めてください"
            ).model_dump_json()
        )
        return None

    if existing["status"] not in ("in_progress", "disconnect"):
        await deps.websocket.send_text(
            ErrorMessage(
                code="session_not_resumable", detail="このセッションは再開できません。新しく始めてください"
            ).model_dump_json()
        )
        return None

    if existing["session_type"] not in ("learning", "review", "explore"):
        await deps.websocket.send_text(
            ErrorMessage(
                code="session_type_mismatch", detail="セッションの種類が正しくありません。新しく始めてください"
            ).model_dump_json()
        )
        return None

    if existing["graph_version"] != GRAPH_VERSION:
        async with deps.pool.acquire() as conn:
            await dialogue_session_repository.abandon_by_id(conn, msg.session_id, deps.user_id)
        await deps.websocket.send_text(
            ErrorMessage(
                code="session_outdated", detail="このセッションは更新により再開できません。新しく始めてください"
            ).model_dump_json()
        )
        return None

    resumed_session_type = cast(Literal["learning", "review", "explore"], existing["session_type"])
    config = build_graph_config(
        session_id=msg.session_id,
        user_id=deps.user_id,
        session_type=resumed_session_type,
        trial=bool(existing.get("is_trial")),
    )

    async with deps.pool.acquire() as conn:
        claimed = await dialogue_session_repository.claim_connection(
            conn, msg.session_id, deps.user_id, deps.connection_id
        )
    if not claimed:
        await deps.websocket.send_text(
            ErrorMessage(
                code="session_not_resumable", detail="このセッションは再開できません。新しく始めてください"
            ).model_dump_json()
        )
        return None

    await _wait_for_turn_to_settle(msg.session_id, deps)
    pending = await _rollback_unanswered_turn(msg.session_id, config, deps)

    async with deps.pool.acquire() as conn:
        last_message_order = await dialogue_message_repository.get_max_message_order(conn, msg.session_id)

    values = await _read_turn_state(deps.graph, config)
    if values is not None:
        _schedule_keywords(values)
    progress = _progress_from_values(values) if values is not None and resumed_session_type == "learning" else None
    end_confirmation = _end_confirmation_from_values(values) if values is not None else None
    await deps.websocket.send_text(
        SessionResumedMessage(
            session_id=msg.session_id,
            session_type=resumed_session_type,
            progress=progress,
            end_confirmation=end_confirmation,
            note_peek_available=values is not None and _note_peek_available_from_values(values),
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


async def _wait_for_turn_to_settle(session_id: UUID, deps: Deps) -> None:
    deadline = asyncio.get_running_loop().time() + TURN_SETTLE_TIMEOUT_SECONDS
    while True:
        async with deps.pool.acquire() as conn:
            if not await dialogue_session_repository.has_turn_in_flight(conn, session_id, TURN_STALE_AFTER):
                return
            if asyncio.get_running_loop().time() >= deadline:
                logger.warning("Turn of session %s did not settle; resuming anyway", session_id)
                await dialogue_session_repository.clear_turn(conn, session_id)
                return
        await asyncio.sleep(TURN_SETTLE_POLL_SECONDS)


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
        storage_key = f"{dialogue_image_prefix(session_id)}{message_id}/{order}.{ext}"
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
    usage_id = await _reserve_llm_usage("turn", deps)
    if usage_id is None:
        has_structured_answer = any(
            value is not None for value in (msg.intake_answers, msg.topic_correction_answer, msg.topic_edit)
        )
        returned = "" if has_structured_answer else msg.content
        await deps.websocket.send_text(PendingMessageRolledBack(content=returned).model_dump_json())
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
            await llm_usage_repository.cancel(conn, usage_id)
            return ctx
        attachments = await _persist_message_images(conn, inserted["id"], ctx.session_id, msg.images)
        await dialogue_session_repository.begin_turn(conn, ctx.session_id, deps.connection_id)

    additional_kwargs: dict[str, Any] = dict(image_attachments_kwargs(attachments))
    if msg.intake_answers is not None:
        additional_kwargs["intake_answers"] = msg.intake_answers.model_dump()
    if topic_correction_answer is not None:
        additional_kwargs["topic_correction_answer"] = topic_correction_answer
    if msg.topic_edit is not None:
        additional_kwargs["topic_edit"] = msg.topic_edit
    if msg.viewed_note:
        additional_kwargs["viewed_note"] = True
    human = HumanMessage(id=str(uuid.uuid4()), content=msg.content, additional_kwargs=additional_kwargs)
    human_config = await deps.graph.aupdate_state(ctx.config, {"messages": [human]}) or ctx.config

    try:
        streamed = await _stream_turn_while_held(human, human_config, ctx, deps)
        turn = streamed if isinstance(streamed, StreamedTurn) else None

        async with deps.pool.acquire() as conn, conn.transaction():
            if turn is not None and not await dialogue_session_repository.finish_turn(
                conn, ctx.session_id, deps.connection_id
            ):
                turn = None
            if turn is not None:
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
        if turn is None and streamed != "stopped":
            await _undo_taken_over_turn(human, human_config, ctx, deps)
            return ctx
    except Exception:
        logger.exception("Turn generation failed for session %s", ctx.session_id)
        async with deps.pool.acquire() as conn:
            held = await dialogue_session_repository.is_held_by(conn, ctx.session_id, deps.connection_id)
        if not held:
            async with deps.pool.acquire() as conn:
                await dialogue_session_repository.clear_turn(conn, ctx.session_id)
            ctx.is_taken_over = True
            return ctx
        pending = await _rollback_unanswered_turn(ctx.session_id, ctx.config, deps)
        async with deps.pool.acquire() as conn:
            await dialogue_session_repository.clear_turn(conn, ctx.session_id)
            await llm_usage_repository.cancel(conn, usage_id)
        ctx.message_order -= 1
        await deps.websocket.send_text(
            ErrorMessage(
                code="turn_failed", detail="問題が発生しました。時間をおいてもう一度お試しください"
            ).model_dump_json()
        )
        if pending is not None:
            await deps.websocket.send_text(PendingMessageRolledBack(content=pending).model_dump_json())
        if deps.inbox.take_ready_if(_is_cancel_request) is not None:
            await deps.websocket.send_text(CancelLastMessageError(detail=_NOTHING_TO_CANCEL_DETAIL).model_dump_json())
        return ctx

    if turn is None:
        await _stop_turn(human, human_config, ctx, deps)
        return ctx
    if turn.end_confirmation_status == "confirmed":
        await _handle_end_session(ctx, deps)
    return ctx


def _is_cancel_request(text: str) -> bool:
    try:
        return isinstance(_incoming_adapter.validate_json(text), CancelLastMessageRequest)
    except ValidationError:
        return False


async def _message_before(human_config: dict[str, Any], deps: Deps) -> BaseMessage | None:
    messages = (await deps.graph.aget_state(human_config)).values.get("messages") or []
    return cast(BaseMessage, messages[-2]) if len(messages) >= 2 else None


async def _stream_turn_while_held(
    human: HumanMessage, human_config: dict[str, Any], ctx: SessionContext, deps: Deps
) -> StreamedTurn | Literal["taken_over", "stopped"]:
    """引き継がれたら "taken_over"、取り消せる発言に停止が届いたら "stopped" を返す。どちらも生成は打ち切る。"""

    async def stream() -> StreamedTurn:
        async with traced_graph_run(ctx.config, name="respond-to-user", input=str(human.content)) as run:
            turn = await _stream_ai_response(
                deps.graph,
                None,
                run.config,
                deps.websocket,
                state_config=ctx.config,
                with_progress=ctx.session_type == "learning",
            )
            run.set_output(turn.content)
        return turn

    async def abandon() -> None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def held() -> bool:
        async with deps.pool.acquire() as conn:
            return await dialogue_session_repository.is_held_by(conn, ctx.session_id, deps.connection_id)

    task = asyncio.create_task(stream())
    watching = True
    try:
        while True:
            waiting: set[asyncio.Future[Any]] = {task, deps.inbox.receiving()} if watching else {task}
            done, _ = await asyncio.wait(
                waiting, timeout=TURN_OWNERSHIP_POLL_SECONDS, return_when=asyncio.FIRST_COMPLETED
            )
            if task in done:
                return task.result()
            if not done:
                if not await held():
                    await abandon()
                    return "taken_over"
                continue
            if deps.inbox.receiving().exception() is not None:
                watching = False
                continue
            text = deps.inbox.take()
            if not _is_cancel_request(text):
                deps.inbox.push_front(text)
                watching = False
                continue
            refusal = _cancel_refusal(human, await _message_before(human_config, deps))
            if refusal is not None:
                await deps.websocket.send_text(CancelLastMessageError(detail=refusal).model_dump_json())
                continue
            is_held = await held()
            if task.done():
                deps.inbox.push_front(text)
                return task.result()
            await abandon()
            return "stopped" if is_held else "taken_over"
    finally:
        task.cancel()


async def _stop_turn(human: HumanMessage, human_checkpoint: dict[str, Any], ctx: SessionContext, deps: Deps) -> None:
    before = (await deps.graph.aget_state(human_checkpoint)).values
    current = (await deps.graph.aget_state(ctx.config)).values
    messages = current.get("messages") or []
    ids = [m.id for m in messages]
    remove = messages[ids.index(human.id) :] if human.id in ids else []
    await deps.graph.aupdate_state(ctx.config, _cancelled_turn_update(before, current, remove))
    async with deps.pool.acquire() as conn:
        await dialogue_message_repository.delete_last_n(conn, ctx.session_id, 1)
        await dialogue_session_repository.clear_turn(conn, ctx.session_id)
    ctx.message_order -= 1
    await _cancel_success(str(human.content), ctx, deps)


async def _undo_taken_over_turn(
    human: HumanMessage, human_checkpoint: dict[str, Any], ctx: SessionContext, deps: Deps
) -> None:
    """発言は state に残し、引き継いだ接続の `_rollback_unanswered_turn` に巻き戻させる。"""
    before_turn = (await deps.graph.aget_state(human_checkpoint)).values
    values = (await deps.graph.aget_state(ctx.config)).values
    messages = values.get("messages") or []
    ids = [m.id for m in messages]
    if human.id in ids:
        added = messages[ids.index(human.id) + 1 :]
        if added or values.get("turn_count") != before_turn.get("turn_count"):
            await deps.graph.aupdate_state(ctx.config, _rewind_update(before_turn, values, added))
    async with deps.pool.acquire() as conn:
        await dialogue_session_repository.clear_turn(conn, ctx.session_id)
    ctx.is_taken_over = True


def _rewind_update(before: dict[str, Any], current: dict[str, Any], remove: Sequence[BaseMessage]) -> dict[str, Any]:
    restored = {k: before.get(k) for k in before.keys() | current.keys() if k != "messages"}
    return {"messages": [RemoveMessage(id=cast(str, m.id)) for m in remove], **restored}


async def _values_before(config: dict[str, Any], message_ids: list[str | None], deps: Deps) -> dict[str, Any] | None:
    async for snapshot in deps.graph.aget_state_history(config):
        messages = snapshot.values.get("messages") or []
        if [m.id for m in messages] == message_ids:
            return cast(dict[str, Any], snapshot.values)
    logger.warning("no checkpoint before the cancelled message; only messages and turn_count are rewound")
    return None


def _cancelled_turn_update(
    before: dict[str, Any] | None, current: dict[str, Any], remove: Sequence[BaseMessage]
) -> dict[str, Any]:
    cleared = {"end_confirmation": None, "pending_topic_correction": None}
    if before is None:
        removed = [RemoveMessage(id=cast(str, m.id)) for m in remove]
        return {"messages": removed, "turn_count": (current.get("turn_count") or 0) - 1, **cleared}
    return {**_rewind_update(before, current, remove), **cleared}


def _cancel_refusal(human: BaseMessage, previous: BaseMessage | None) -> str | None:
    if "topic_edit" in human.additional_kwargs:
        return "トピックの変更は取り消せません"
    if "topic_correction_answer" in human.additional_kwargs or (
        previous is not None and "topic_correction_card" in previous.additional_kwargs
    ):
        return "トピックの変更への回答は取り消せません"
    if "intake_answers" in human.additional_kwargs or (
        previous is not None and "intake_card" in previous.additional_kwargs
    ):
        return "聞き取りへの回答は取り消せません"
    return None


async def _cancel_success(content: str, ctx: SessionContext, deps: Deps) -> None:
    values = await _read_turn_state(deps.graph, ctx.config)
    progress = _progress_from_values(values) if values is not None and ctx.session_type == "learning" else None
    await deps.websocket.send_text(
        CancelLastMessageSuccess(
            cancelled_content=content,
            progress=progress,
            note_peek_available=values is not None and _note_peek_available_from_values(values),
        ).model_dump_json()
    )


async def _handle_cancel_last_message(ctx: SessionContext, deps: Deps) -> SessionContext:
    if ctx.message_order < 4:
        await deps.websocket.send_text(CancelLastMessageError(detail=_NOTHING_TO_CANCEL_DETAIL).model_dump_json())
        return ctx

    state = await deps.graph.aget_state(ctx.config)
    messages_in_state = state.values["messages"]

    last_ai = messages_in_state[-1]
    last_human = messages_in_state[-2]
    previous = messages_in_state[-3] if len(messages_in_state) >= 3 else None
    if (refusal := _cancel_refusal(last_human, previous)) is not None:
        await deps.websocket.send_text(CancelLastMessageError(detail=refusal).model_dump_json())
        return ctx

    cancelled_content = str(last_human.content)

    before = await _values_before(ctx.config, [m.id for m in messages_in_state[:-2]], deps)
    await deps.graph.aupdate_state(ctx.config, _cancelled_turn_update(before, state.values, [last_ai, last_human]))

    async with deps.pool.acquire() as conn:
        await dialogue_message_repository.delete_last_n(conn, ctx.session_id, 2)
    ctx.message_order -= 2

    await _cancel_success(cancelled_content, ctx, deps)
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


async def _taken_over(ctx: SessionContext | None, deps: Deps) -> bool:
    if ctx is None:
        return False
    async with deps.pool.acquire() as conn:
        return not await dialogue_session_repository.is_held_by(conn, ctx.session_id, deps.connection_id)


async def _close_taken_over(websocket: WebSocket) -> None:
    with contextlib.suppress(Exception):
        await websocket.send_text(SessionTakenOver(detail=_TAKEN_OVER_DETAIL).model_dump_json())
        await websocket.close()


_PROTOCOL_MISMATCH_DETAIL = "アプリが更新されました。ページを再読み込みしてください"
_CONSENT_REQUIRED_DETAIL = "利用規約とプライバシーポリシーへの同意が必要です。ページを再読み込みしてください"


async def _refuse_connection(websocket: WebSocket, error: ErrorMessage) -> None:
    """閉じるとクライアントは自動で再接続を繰り返すので、開いたまま、届いた発言のたびに同じエラーを返す。"""
    error_json = error.model_dump_json()
    with contextlib.suppress(WebSocketDisconnect):
        await websocket.send_text(error_json)
        while True:
            await websocket.receive_text()
            await websocket.send_text(error_json)


router = APIRouter()


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        auth = await authenticate_websocket(websocket)
    except ValueError:
        return
    if auth.protocol_version != PROTOCOL_VERSION:
        await _refuse_connection(
            websocket, ErrorMessage(code="protocol_version_mismatch", detail=_PROTOCOL_MISMATCH_DETAIL)
        )
        return
    user_id = auth.user_id
    pool = await get_pool()
    async with pool.acquire() as conn:
        consented = await user_consent_repository.has_consented(conn, user_id, TERMS_VERSION)
    if not consented:
        await _refuse_connection(websocket, ErrorMessage(code="consent_required", detail=_CONSENT_REQUIRED_DETAIL))
        return

    deps = Deps(
        pool=pool,
        graph=websocket.app.state.graph,
        websocket=websocket,
        user_id=user_id,
        connection_id=uuid.uuid4(),
        inbox=Inbox(websocket),
    )

    ctx: SessionContext | None = None

    try:
        while True:
            user_input = await deps.inbox.next()

            try:
                msg = _incoming_adapter.validate_json(user_input)
            except ValidationError as exc:
                await websocket.send_text(
                    ErrorMessage(code="invalid_message", detail=_validation_error_detail(exc)).model_dump_json()
                )
                continue

            if isinstance(msg, UserMessage | CancelLastMessageRequest | EndSessionMessage) and await _taken_over(
                ctx, deps
            ):
                await _close_taken_over(websocket)
                break

            if isinstance(
                msg, StartLearningMessage | StartExploreMessage | StartSynthesisMessage | StartReviewMessage
            ):
                usage_id = await _reserve_llm_usage("session_start", deps)
                if usage_id is None:
                    continue
                if isinstance(msg, StartLearningMessage):
                    new_ctx: SessionContext | None = await _handle_start_learning(msg, deps)
                elif isinstance(msg, StartExploreMessage):
                    new_ctx = await _handle_start_explore(msg, deps)
                elif isinstance(msg, StartSynthesisMessage):
                    new_ctx = await _handle_start_synthesis(msg, deps)
                else:
                    new_ctx = await _handle_start_review(msg, deps)
                if new_ctx is None:
                    await _cancel_llm_usage(usage_id, deps)
                else:
                    ctx = new_ctx
            elif isinstance(msg, ResumeSessionMessage):
                new_ctx = await _handle_resume_session(msg, deps)
                if new_ctx is not None:
                    ctx = new_ctx
            elif isinstance(msg, UserMessage):
                if ctx is None:
                    await websocket.send_text(
                        ErrorMessage(
                            code="session_not_started",
                            detail="セッションが開始されていません。ページを再読み込みしてください",
                        ).model_dump_json()
                    )
                    continue
                ctx = await _handle_user_message(msg, ctx, deps)
                if ctx.is_taken_over:
                    await _close_taken_over(websocket)
                    break
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
                await dialogue_session_repository.release_connection(
                    conn, ctx.session_id, deps.connection_id, "disconnect"
                )
    except Exception:
        logger.exception(
            "WebSocket handler crashed",
            extra={"session_id": str(ctx.session_id) if ctx else None},
        )
        if ctx is not None:
            async with deps.pool.acquire() as conn:
                await dialogue_session_repository.release_connection(
                    conn, ctx.session_id, deps.connection_id, "failed"
                )
        await websocket.send_text(
            ErrorMessage(
                code="internal_error", detail="問題が発生しました。時間をおいてもう一度お試しください"
            ).model_dump_json()
        )
    finally:
        deps.inbox.close()
