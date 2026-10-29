import re
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from api.dependencies import CurrentUser
from api.errors import ApiError, ErrorCode
from core import config
from core.image_signature import detect_image_mime
from schemas.avatar import AvatarResponse
from storage import ObjectStorage, avatar_prefix, get_storage

router = APIRouter(tags=["avatar"])

_EXT_BY_MIME = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
_MIME_BY_EXT = {ext: mime for mime, ext in _EXT_BY_MIME.items()}
_USER_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
_FILENAME = re.compile(r"[0-9a-f]{32}\.(jpg|png|webp)")
_CACHE_CONTROL = "public, max-age=31536000, immutable"

Storage = Annotated[ObjectStorage, Depends(get_storage)]


def _avatar_path(user_id: str, filename: str) -> str:
    return f"/api/avatars/{user_id}/{filename}"


def _require_safe_user_id(user_id: str) -> None:
    if not _USER_ID.fullmatch(user_id):
        raise ApiError(status.HTTP_400_BAD_REQUEST, ErrorCode.VALIDATION_ERROR, "Invalid user id")


@router.put("/api/account/avatar", response_model=AvatarResponse)
async def upload_avatar(
    current_user_id: CurrentUser,
    storage: Storage,
    file: Annotated[UploadFile, File()],
) -> AvatarResponse:
    _require_safe_user_id(current_user_id)
    data = await file.read(config.MAX_AVATAR_BYTES + 1)
    if not data:
        raise ApiError(status.HTTP_400_BAD_REQUEST, ErrorCode.AVATAR_EMPTY, "Avatar is empty")
    if len(data) > config.MAX_AVATAR_BYTES:
        raise ApiError(status.HTTP_413_CONTENT_TOO_LARGE, ErrorCode.AVATAR_TOO_LARGE, "Avatar is too large")
    mime_type = detect_image_mime(data)
    if mime_type not in _EXT_BY_MIME:
        raise ApiError(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, ErrorCode.UNSUPPORTED_AVATAR_FORMAT, "Unsupported avatar format"
        )

    prefix = avatar_prefix(current_user_id)
    await storage.delete_prefix(prefix)
    filename = f"{uuid4().hex}.{_EXT_BY_MIME[mime_type]}"
    await storage.put(f"{prefix}{filename}", data, mime_type)
    return AvatarResponse(path=_avatar_path(current_user_id, filename))


@router.delete("/api/account/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def delete_avatar(current_user_id: CurrentUser, storage: Storage) -> Response:
    _require_safe_user_id(current_user_id)
    await storage.delete_prefix(avatar_prefix(current_user_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/avatars/{user_id}/{filename}")
async def get_avatar(user_id: str, filename: str, storage: Storage) -> Response:
    if not (_USER_ID.fullmatch(user_id) and _FILENAME.fullmatch(filename)):
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.AVATAR_NOT_FOUND, "Avatar not found")
    try:
        data = await storage.get(f"{avatar_prefix(user_id)}{filename}")
    except FileNotFoundError as exc:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.AVATAR_NOT_FOUND, "Avatar not found") from exc
    return Response(
        content=data,
        media_type=_MIME_BY_EXT[filename.rsplit(".", 1)[1]],
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": _CACHE_CONTROL},
    )
