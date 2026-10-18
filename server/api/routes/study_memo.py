from uuid import UUID

from fastapi import APIRouter, status

from api.dependencies import DB, CurrentUser
from api.errors import ApiError, ErrorCode
from repositories import study_memo_repository
from schemas.study_memo import StudyMemoListResponse, StudyMemoResponse, StudyMemoSummary, StudyMemoUpdate
from services.study_memo_edit import StudyMemoEditError, apply_study_memo_edit

router = APIRouter(prefix="/api/study-memos", tags=["study-memos"])


@router.get("", response_model=StudyMemoListResponse)
async def list_study_memos(current_user_id: CurrentUser, db: DB) -> StudyMemoListResponse:
    records = await study_memo_repository.find_by_user_id(db, current_user_id)
    return StudyMemoListResponse(memos=[StudyMemoSummary(**r, aspects=r["overview"]) for r in records])


@router.get("/{memo_id}", response_model=StudyMemoResponse)
async def get_study_memo(memo_id: UUID, current_user_id: CurrentUser, db: DB) -> StudyMemoResponse:
    memo = await study_memo_repository.find_by_id(db, memo_id, current_user_id)
    if memo is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.STUDY_MEMO_NOT_FOUND, "Study memo not found")
    return StudyMemoResponse.model_validate(memo)


@router.patch("/{memo_id}", response_model=StudyMemoResponse)
async def update_study_memo(
    memo_id: UUID, memo_data: StudyMemoUpdate, current_user_id: CurrentUser, db: DB
) -> StudyMemoResponse:
    async with db.transaction():
        memo = await study_memo_repository.find_by_id_for_update(db, memo_id, current_user_id)
        if memo is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.STUDY_MEMO_NOT_FOUND, "Study memo not found")
        try:
            changes = apply_study_memo_edit(memo, memo_data)
        except StudyMemoEditError as exc:
            raise ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.VALIDATION_ERROR, str(exc)) from exc
        updated = await study_memo_repository.update(db, memo_id, current_user_id, changes)
    assert updated is not None
    return StudyMemoResponse.model_validate(updated)


@router.delete("/{memo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_study_memo(memo_id: UUID, current_user_id: CurrentUser, db: DB) -> None:
    if not await study_memo_repository.delete(db, memo_id, current_user_id):
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.STUDY_MEMO_NOT_FOUND, "Study memo not found")
