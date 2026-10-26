from typing import Annotated, Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, status

from api.dependencies import DB, Checkpointer, ConsentedUser, CurrentUser
from api.errors import ApiError, ErrorCode
from core import config
from core.database import get_pool
from repositories import (
    collection_synthesis_repository,
    llm_usage_repository,
    note_collection_repository,
    note_repository,
    synthesis_insight_repository,
)
from schemas.note_collection import (
    CollectionCreate,
    CollectionDetailResponse,
    CollectionListResponse,
    CollectionNote,
    CollectionRename,
    CollectionResponse,
    CollectionSummary,
    SynthesisInsight,
    SynthesisResponse,
)
from services.collection_synthesis import (
    CollectionDeletedDuringSynthesisError,
    CollectionNotFoundError,
    NoteCountError,
    Staleness,
    SynthesisGenerationError,
    generate_synthesis,
    staleness,
    to_source_notes,
)
from services.note_deletion import delete_collection as delete_collection_and_sessions
from services.review_scheduler import is_established
from storage import ObjectStorage, get_storage

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
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.COLLECTION_NOT_FOUND, "Collection not found")
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
        raise ApiError(
            status.HTTP_409_CONFLICT, ErrorCode.COLLECTION_NAME_TAKEN, "Collection name already exists"
        ) from exc
    if record is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.COLLECTION_NOT_FOUND, "Collection not found")
    return CollectionResponse(**record)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: UUID,
    current_user_id: CurrentUser,
    db: DB,
    checkpointer: Checkpointer,
    storage: Annotated[ObjectStorage, Depends(get_storage)],
) -> None:
    if not await delete_collection_and_sessions(db, checkpointer, storage, collection_id, current_user_id):
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.COLLECTION_NOT_FOUND, "Collection not found")


def _synthesis_response(record: dict[str, Any], state: Staleness, insights: list[dict[str, Any]]) -> SynthesisResponse:
    return SynthesisResponse(
        collection_id=record["collection_id"],
        content=record["content"],
        connections=record["connections"],
        contradictions=record["contradictions"],
        gaps=record["gaps"],
        generated_at=record["generated_at"],
        is_stale=state.is_stale,
        changed_note_ids=[UUID(note_id) for note_id in state.changed_note_ids],
        insights=[SynthesisInsight(**i) for i in insights],
    )


@router.get("/{collection_id}/synthesis", response_model=SynthesisResponse)
async def get_synthesis(collection_id: UUID, current_user_id: CurrentUser, db: DB) -> SynthesisResponse:
    record = await collection_synthesis_repository.find_by_collection_id(db, collection_id, current_user_id)
    if record is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.SYNTHESIS_NOT_FOUND, "Synthesis not found")
    current = to_source_notes(await note_repository.find_contents_by_collection_id(db, collection_id, current_user_id))
    insights = await synthesis_insight_repository.find_by_collection_id(db, collection_id, current_user_id)
    return _synthesis_response(record, staleness(record["source_notes"], current), insights)


async def _cancel_reservation(usage_id: UUID) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await llm_usage_repository.cancel(conn, usage_id)


@router.post("/{collection_id}/synthesis", response_model=SynthesisResponse)
async def create_synthesis(collection_id: UUID, current_user_id: ConsentedUser) -> SynthesisResponse:
    pool = await get_pool()
    async with pool.acquire() as conn:
        usage_id = await llm_usage_repository.reserve(
            conn, current_user_id, "synthesis", config.REVIEW_TIMEZONE, config.DAILY_SYNTHESIS_LIMIT
        )
    if usage_id is None:
        raise ApiError(
            status.HTTP_429_TOO_MANY_REQUESTS, ErrorCode.DAILY_SYNTHESIS_LIMIT_REACHED, "Daily synthesis limit reached"
        )
    try:
        record = await generate_synthesis(collection_id, current_user_id)
    except CollectionDeletedDuringSynthesisError as exc:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.COLLECTION_NOT_FOUND, "Collection not found") from exc
    except CollectionNotFoundError as exc:
        await _cancel_reservation(usage_id)
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.COLLECTION_NOT_FOUND, "Collection not found") from exc
    except NoteCountError as exc:
        await _cancel_reservation(usage_id)
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ErrorCode.COLLECTION_NOTE_COUNT_OUT_OF_RANGE,
            "Collection needs 2 to 30 notes",
        ) from exc
    except SynthesisGenerationError as exc:
        raise ApiError(status.HTTP_502_BAD_GATEWAY, ErrorCode.SYNTHESIS_FAILED, "Synthesis generation failed") from exc
    pool = await get_pool()
    async with pool.acquire() as conn:
        insights = await synthesis_insight_repository.find_by_collection_id(conn, collection_id, current_user_id)
    return _synthesis_response(record, Staleness(is_stale=False, changed_note_ids=[]), insights)
