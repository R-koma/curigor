from fastapi import APIRouter, Response, status

from api.dependencies import DB, CurrentUser
from api.errors import ApiError, ErrorCode
from core.terms import TERMS_VERSION
from repositories import user_consent_repository
from schemas.consent import ConsentRequest, ConsentStatusResponse

router = APIRouter(prefix="/api/consents", tags=["consents"])


@router.get("/me", response_model=ConsentStatusResponse)
async def get_my_consent(current_user_id: CurrentUser, db: DB) -> ConsentStatusResponse:
    consented = await user_consent_repository.has_consented(db, current_user_id, TERMS_VERSION)
    return ConsentStatusResponse(terms_version=TERMS_VERSION, consented=consented)


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def consent(body: ConsentRequest, current_user_id: CurrentUser, db: DB) -> Response:
    if body.terms_version != TERMS_VERSION:
        raise ApiError(status.HTTP_409_CONFLICT, ErrorCode.TERMS_VERSION_OUTDATED, "Terms have been updated")
    await user_consent_repository.record(db, current_user_id, TERMS_VERSION)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
