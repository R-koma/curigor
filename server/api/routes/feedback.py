from uuid import UUID

from fastapi import APIRouter, status

from api.dependencies import DB, CurrentUser
from api.errors import ApiError, ErrorCode
from repositories import feedback_repository, note_repository
from schemas.feedback import FeedbackListResponse, FeedbackResponse

router = APIRouter(prefix="/api/notes/{note_id}/feedbacks", tags=["feedbacks"])


@router.get("", response_model=FeedbackListResponse)
async def list_feedbacks(note_id: UUID, current_user_id: CurrentUser, db: DB) -> FeedbackListResponse:
    if await note_repository.find_by_id(db, note_id, current_user_id) is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.NOTE_NOT_FOUND, "Note not found")
    records = await feedback_repository.find_by_note_id(db, note_id, current_user_id)
    return FeedbackListResponse(feedbacks=[FeedbackResponse(**r) for r in records])
