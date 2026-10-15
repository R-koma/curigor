from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.auth import verify_jwt
from core.database import DBConnection, get_pool

security = HTTPBearer()
BearerCredentials = Annotated[HTTPAuthorizationCredentials, Security(security)]


async def get_current_user(credentials: BearerCredentials) -> str:
    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = verify_jwt(token)
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        return user_id
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e


async def get_db() -> AsyncGenerator[DBConnection]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


CurrentUser = Annotated[str, Depends(get_current_user)]
DB = Annotated[DBConnection, Depends(get_db)]
