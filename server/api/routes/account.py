from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from api.dependencies import AccountDeletionUser
from core.database import get_pool
from services.account_deletion import purge_user_data
from storage import ObjectStorage, get_storage

router = APIRouter(prefix="/api/account", tags=["account"])


@router.delete("/data", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account_data(
    current_user_id: AccountDeletionUser,
    request: Request,
    storage: Annotated[ObjectStorage, Depends(get_storage)],
) -> Response:
    pool = await get_pool()
    await purge_user_data(pool, request.app.state.checkpointer, storage, current_user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
