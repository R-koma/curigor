from typing import Any
from uuid import UUID

from langchain_core.messages import SystemMessage

from core.database import DBConnection, get_pool
from graph.aspect_map import feedback_insert_fields, parse_aspect_map
from graph.llm import llm_structured
from graph.nodes._feedback_assessment import (
    analyze_dialogue,
    format_conversation_history,
    format_note_text,
    score_feedback,
)
from graph.output_schemas import NoteContent, ReviewAddendum
from graph.prompts import APPEND_REVIEW_PROMPT, UPDATE_NOTE_PROMPT
from graph.state import LearningState
from repositories import feedback_repository, note_repository, note_revision_repository, review_schedule_repository
from services.note_embedding import schedule_note_embedding
from services.review_scheduler import calculate_next_review, is_early_review


async def update_note_and_feedback(state: LearningState) -> dict[str, Any]:
    """復習対話の内容で既存ノートを更新し、フィードバックを UPSERT する。

    手動編集済みノート（manually_edited_at あり）は base 本文を保全し、AI 改訂を note_revisions へ
    追記する（追記専用）。未編集ノートは従来どおり base 本文をフル改訂で上書きする（ADR-005 / #235）。
    """

    pool = await get_pool()
    note_id = state["note_id"]
    user_id = state["user_id"]

    conversation_history = format_conversation_history(state["messages"])

    async with pool.acquire() as conn:
        existing_note = await note_repository.find_by_id(conn, note_id, user_id)
        if not existing_note:
            raise RuntimeError(f"Note {note_id} not found")

        topic = existing_note["topic"]

        if existing_note["manually_edited_at"] is not None:
            feedback_content = await _append_review_revision(
                conn=conn,
                state=state,
                topic=topic,
                base_content=existing_note["content"],
                conversation_history=conversation_history,
            )
        else:
            feedback_content = await _regenerate_note(
                conn=conn,
                note_id=note_id,
                user_id=user_id,
                topic=topic,
                summary=existing_note["summary"] or "",
                content=existing_note["content"],
                conversation_history=conversation_history,
            )

        await _update_feedback(
            conn=conn,
            state=state,
            topic=topic,
            note_content=feedback_content,
            conversation_history=conversation_history,
            aspect_map=parse_aspect_map(existing_note["aspect_map"]),
        )
        await _advance_review_schedule(conn=conn, note_id=note_id)

    schedule_note_embedding(note_id, user_id)
    return {}


async def _regenerate_note(
    conn: DBConnection,
    note_id: UUID,
    user_id: str,
    topic: str,
    summary: str,
    content: str,
    conversation_history: str,
) -> str:
    """未編集ノート: base 本文をフル改訂で上書きし、改訂後の本文を返す。"""

    update_note_prompt = UPDATE_NOTE_PROMPT.format(
        topic=topic,
        summary=summary,
        content=content,
        conversation_history=conversation_history,
    )
    note_structured_llm = llm_structured.with_structured_output(NoteContent, task="revise-note")
    revised_note = await note_structured_llm.ainvoke(
        [SystemMessage(content=update_note_prompt)],
        config={"run_name": "revise-note"},
    )
    if not isinstance(revised_note, NoteContent):
        raise RuntimeError("LLM did not return structured NoteContent output")

    await note_repository.update(
        conn=conn,
        note_id=note_id,
        user_id=user_id,
        content=revised_note.content,
        summary=revised_note.summary,
    )
    return revised_note.content


async def _append_review_revision(
    conn: DBConnection,
    state: LearningState,
    topic: str,
    base_content: str,
    conversation_history: str,
) -> str:
    """手動編集済みノート: base 本文を保全し、復習の追記を note_revisions に保存する。

    base 本文は LLM 出力に通さずそのまま残るため byte 単位で保全される。フィードバックは
    base 本文に対して生成する（追記は base への補足であり、評価対象は手動編集後のノート本体）。
    """

    append_prompt = APPEND_REVIEW_PROMPT.format(
        topic=topic,
        content=base_content,
        conversation_history=conversation_history,
    )
    addendum_llm = llm_structured.with_structured_output(ReviewAddendum, task="append-review-addendum")
    addendum = await addendum_llm.ainvoke(
        [SystemMessage(content=append_prompt)],
        config={"run_name": "append-review-addendum"},
    )
    if not isinstance(addendum, ReviewAddendum):
        raise RuntimeError("LLM did not return structured ReviewAddendum output")

    await note_revision_repository.insert(
        conn=conn,
        note_id=state["note_id"],
        dialogue_session_id=state["dialogue_session_id"],
        content=addendum.content,
    )
    return base_content


async def _update_feedback(
    conn: DBConnection,
    state: LearningState,
    topic: str,
    note_content: str,
    conversation_history: str,
    aspect_map: dict[str, Any] | None,
) -> None:
    analysis = await analyze_dialogue(topic, conversation_history)
    feedback_data = await score_feedback(topic, analysis, aspect_map, format_note_text(topic, note_content))

    await feedback_repository.insert(
        conn=conn,
        note_id=state["note_id"],
        dialogue_session_id=state["dialogue_session_id"],
        understanding_level=feedback_data.understanding_level,
        **feedback_insert_fields(feedback_data, aspect_map),
    )


async def _advance_review_schedule(conn: DBConnection, note_id: UUID) -> None:
    schedule = await review_schedule_repository.find_by_note_id(conn=conn, note_id=note_id)
    if schedule is None:
        await review_schedule_repository.insert(conn=conn, note_id=note_id, next_review_at=calculate_next_review(0))
        return
    if is_early_review(schedule["next_review_at"]):
        return

    completed_reviews: int = schedule["review_count"] + 1
    await review_schedule_repository.update_schedule(
        conn=conn,
        note_id=note_id,
        review_count=completed_reviews,
        next_review_at=calculate_next_review(completed_reviews),
    )
