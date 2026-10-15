from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langgraph.checkpoint.base import BaseCheckpointSaver

from core.auth import verify_jwt
from core.database import DBConnection, get_pool

security = HTTPBearer()
BearerCredentials = Annotated[HTTPAuthorizationCredentials, Security(security)]


ACCOUNT_DELETION_PURPOSE = "account-deletion"


def _verified_payload(credentials: HTTPAuthorizationCredentials) -> dict[str, Any]:
    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = verify_jwt(token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    if not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return payload


async def get_current_user(credentials: BearerCredentials) -> str:
    user_id: str = _verified_payload(credentials)["sub"]
    return user_id


async def get_account_deletion_user(credentials: BearerCredentials) -> str:
    payload = _verified_payload(credentials)
    if payload.get("purpose") != ACCOUNT_DELETION_PURPOSE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token is not for account deletion")
    user_id: str = payload["sub"]
    return user_id


async def get_db() -> AsyncGenerator[DBConnection]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


def get_app_checkpointer(request: Request) -> BaseCheckpointSaver[Any]:
    checkpointer: BaseCheckpointSaver[Any] = request.app.state.checkpointer
    return checkpointer


CurrentUser = Annotated[str, Depends(get_current_user)]
AccountDeletionUser = Annotated[str, Depends(get_account_deletion_user)]
DB = Annotated[DBConnection, Depends(get_db)]
Checkpointer = Annotated[BaseCheckpointSaver[Any], Depends(get_app_checkpointer)]
