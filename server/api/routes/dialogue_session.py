from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from api.dependencies import DB, CurrentUser
from repositories import (
    dialogue_message_image_repository,
    dialogue_message_repository,
    dialogue_session_repository,
    feedback_repository,
    note_repository,
)
from schemas.dialogue_session import (
    ActiveSessionResponse,
    DialogueImageData,
    DialogueMessageData,
    FeedbackData,
    NoteStatusResponse,
    SessionMessagesResponse,
)
from schemas.intake_card import IntakeCard
from storage import get_storage

router = APIRouter(prefix="/api/dialogue-sessions", tags=["dialogue-sessions"])


@router.get("/active", response_model=ActiveSessionResponse | None)
async def get_active_session(
    current_user_id: CurrentUser,
    db: DB,
) -> Response | ActiveSessionResponse:
    session = await dialogue_session_repository.find_resumable_by_user(db, current_user_id)
    if not session:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return ActiveSessionResponse(
        session_id=session["id"],
        session_type=session["session_type"],
        status=session["status"],
        started_at=session["started_at"],
        topic=session.get("topic"),
        note_id=session.get("note_id"),
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def abandon_session(
    session_id: UUID,
    current_user_id: CurrentUser,
    db: DB,
) -> Response:
    session = await dialogue_session_repository.find_by_id(db, session_id, current_user_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    await dialogue_session_repository.abandon_by_id(db, session_id, current_user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{session_id}/messages", response_model=SessionMessagesResponse)
async def get_session_messages(
    session_id: UUID,
    current_user_id: CurrentUser,
    db: DB,
) -> SessionMessagesResponse:
    session = await dialogue_session_repository.find_by_id(db, session_id, current_user_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    messages = await dialogue_message_repository.find_by_session_id(db, session_id)
    images = await dialogue_message_image_repository.find_by_session_id(db, session_id)

    images_by_message: dict[UUID, list[DialogueImageData]] = defaultdict(list)
    for img in images:
        images_by_message[img["dialogue_message_id"]].append(
            DialogueImageData(id=img["id"], mime_type=img["mime_type"], image_order=img["image_order"])
        )

    return SessionMessagesResponse(
        session_id=session["id"],
        session_type=session["session_type"],
        status=session["status"],
        note_id=session["note_id"],
        topic=session.get("topic"),
        messages=[
            DialogueMessageData(
                role=m["role"],
                content=m["content"],
                message_order=m["message_order"],
                images=images_by_message.get(m["id"], []),
                intake_card=IntakeCard.model_validate_json(m["intake_card"]) if m.get("intake_card") else None,
            )
            for m in messages
        ],
    )


@router.get("/{session_id}/images/{image_id}")
async def get_session_image(
    session_id: UUID,
    image_id: UUID,
    current_user_id: CurrentUser,
    db: DB,
) -> Response:
    session = await dialogue_session_repository.find_by_id(db, session_id, current_user_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    image = await dialogue_message_image_repository.find_in_session(db, session_id, image_id)
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    data = await get_storage().get(image["storage_key"])
    # 保存 mime は実体と一致する保証がないため、ブラウザの
    # MIME スニッフィングを抑止する（多層防御）。
    return Response(
        content=data,
        media_type=image["mime_type"],
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/{session_id}/note-status", response_model=NoteStatusResponse)
async def get_note_status(
    session_id: UUID,
    current_user_id: CurrentUser,
    db: DB,
) -> NoteStatusResponse:
    session = await dialogue_session_repository.find_by_id(db, session_id, current_user_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    response = NoteStatusResponse(
        status=session["status"],
        session_type=session["session_type"],
    )

    if session["status"] != "completed" or session["note_id"] is None:
        return response

    if session["session_type"] == "learning":
        note = await note_repository.find_by_id(db, session["note_id"], current_user_id)
        if note:
            response.note_id = note["id"]
            response.topic = note["topic"]
            response.summary = note["summary"] or ""
    else:
        note = await note_repository.find_by_id(db, session["note_id"], current_user_id)
        if note:
            response.note_id = note["id"]
            response.topic = note["topic"]
            response.summary = note["summary"] or ""
        feedbacks = await feedback_repository.find_by_note_id(db, session["note_id"], current_user_id)
        if feedbacks:
            latest = feedbacks[-1]
            response.feedback = FeedbackData(
                understanding_level=latest["understanding_level"],
                strength=latest["strength"],
                improvements=latest["improvements"],
            )

    return response
