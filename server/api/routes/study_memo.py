from uuid import UUID

from fastapi import APIRouter, status

from api.dependencies import DB, CurrentUser
from api.errors import ApiError, ErrorCode
from repositories import study_memo_repository
from schemas.study_memo import StudyMemoListResponse, StudyMemoResponse, StudyMemoSummary

router = APIRouter(prefix="/api/study-memos", tags=["study-memos"])


@router.get("", response_model=StudyMemoListResponse)
async def list_study_memos(current_user_id: CurrentUser, db: DB) -> StudyMemoListResponse:
    records = await study_memo_repository.find_by_user_id(db, current_user_id)
    return StudyMemoListResponse(memos=[StudyMemoSummary(**r) for r in records])


@router.get("/{memo_id}", response_model=StudyMemoResponse)
async def get_study_memo(memo_id: UUID, current_user_id: CurrentUser, db: DB) -> StudyMemoResponse:
    memo = await study_memo_repository.find_by_id(db, memo_id, current_user_id)
    if memo is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.STUDY_MEMO_NOT_FOUND, "Study memo not found")
    return StudyMemoResponse.model_validate(memo)
