from uuid import UUID

from fastapi import APIRouter, status

from api.dependencies import DB, CurrentUser
from api.errors import ApiError, ErrorCode
from repositories import note_repository, note_revision_repository
from schemas.note_revision import NoteRevisionListResponse, NoteRevisionResponse

router = APIRouter(prefix="/api/notes/{note_id}/revisions", tags=["note-revisions"])


@router.get("", response_model=NoteRevisionListResponse)
async def list_note_revisions(note_id: UUID, current_user_id: CurrentUser, db: DB) -> NoteRevisionListResponse:
    if await note_repository.find_by_id(db, note_id, current_user_id) is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.NOTE_NOT_FOUND, "Note not found")
    records = await note_revision_repository.find_by_note_id(db, note_id, current_user_id)
    return NoteRevisionListResponse(revisions=[NoteRevisionResponse(**r) for r in records])
