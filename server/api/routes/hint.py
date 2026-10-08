from fastapi import APIRouter, Response, status

from api.dependencies import DB, CurrentUser
from repositories import hint_dismissal_repository
from schemas.hint import HintDismissalsResponse, HintId

router = APIRouter(prefix="/api/hints", tags=["hints"])


@router.get("/dismissals", response_model=HintDismissalsResponse)
async def list_hint_dismissals(current_user_id: CurrentUser, db: DB) -> HintDismissalsResponse:
    hint_ids = await hint_dismissal_repository.find_hint_ids_by_user(db, current_user_id)
    return HintDismissalsResponse(dismissed=hint_ids)


@router.put("/dismissals/{hint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_hint(hint_id: HintId, current_user_id: CurrentUser, db: DB) -> Response:
    await hint_dismissal_repository.dismiss(db, current_user_id, hint_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/dismissals", status_code=status.HTTP_204_NO_CONTENT)
async def reset_hint_dismissals(current_user_id: CurrentUser, db: DB) -> Response:
    await hint_dismissal_repository.delete_all_by_user(db, current_user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
