from uuid import UUID

import asyncpg
from fastapi import APIRouter, HTTPException, status

from api.dependencies import DB, CurrentUser
from repositories import note_collection_repository, note_repository
from schemas.note_collection import (
    CollectionCreate,
    CollectionDetailResponse,
    CollectionListResponse,
    CollectionNote,
    CollectionRename,
    CollectionResponse,
    CollectionSummary,
)
from services.review_scheduler import is_established

router = APIRouter(prefix="/api/collections", tags=["collections"])


@router.get("", response_model=CollectionListResponse)
async def list_collections(current_user_id: CurrentUser, db: DB) -> CollectionListResponse:
    records = await note_collection_repository.find_by_user_id(db, current_user_id)
    return CollectionListResponse(collections=[CollectionSummary(**r) for r in records])


@router.post("", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(body: CollectionCreate, current_user_id: CurrentUser, db: DB) -> CollectionResponse:
    record = await note_collection_repository.get_or_create(db, current_user_id, body.name)
    return CollectionResponse(**record)


@router.get("/{collection_id}", response_model=CollectionDetailResponse)
async def get_collection(collection_id: UUID, current_user_id: CurrentUser, db: DB) -> CollectionDetailResponse:
    collection = await note_collection_repository.find_by_id(db, collection_id, current_user_id)
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    notes = await note_repository.find_by_collection_id(db, collection_id, current_user_id)
    return CollectionDetailResponse(
        **collection,
        notes=[CollectionNote(**n, is_established=is_established(n["review_count"])) for n in notes],
    )


@router.patch("/{collection_id}", response_model=CollectionResponse)
async def rename_collection(
    collection_id: UUID, body: CollectionRename, current_user_id: CurrentUser, db: DB
) -> CollectionResponse:
    try:
        record = await note_collection_repository.rename(db, collection_id, current_user_id, body.name)
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Collection name already exists") from exc
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return CollectionResponse(**record)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(collection_id: UUID, current_user_id: CurrentUser, db: DB) -> None:
    if not await note_collection_repository.delete(db, collection_id, current_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
