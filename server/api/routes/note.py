from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from api.dependencies import DB, CurrentUser
from repositories import note_collection_repository, note_link_repository, note_repository
from schemas.note import NoteListResponse, NoteResponse, NoteUpdate
from schemas.note_collection import NoteCollectionAssign
from schemas.note_link import LinkedNote, NoteLinkListResponse, NoteLinkResponse, NoteLinkUpdate
from services.note_embedding import schedule_note_embedding

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("", response_model=NoteListResponse)
async def list_notes(current_user_id: CurrentUser, db: DB) -> NoteListResponse:
    records = await note_repository.find_by_user_id(db, current_user_id)
    return NoteListResponse(notes=[NoteResponse(**r) for r in records])


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(note_id: UUID, current_user_id: CurrentUser, db: DB) -> NoteResponse:
    record = await note_repository.find_by_id(db, note_id, current_user_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    return NoteResponse(**record)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(note_id: UUID, note_data: NoteUpdate, current_user_id: CurrentUser, db: DB) -> NoteResponse:
    update_data = note_data.model_dump(exclude_unset=True)
    mark_manually_edited = any(field in update_data for field in ("topic", "summary", "content"))
    record = await note_repository.update(
        db, note_id=note_id, user_id=current_user_id, mark_manually_edited=mark_manually_edited, **update_data
    )

    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    if mark_manually_edited:
        schedule_note_embedding(note_id, current_user_id)
    return NoteResponse(**record)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: UUID, current_user_id: CurrentUser, db: DB) -> None:
    success = await note_repository.delete(db, note_id, current_user_id)

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")


@router.put("/{note_id}/collection", status_code=status.HTTP_204_NO_CONTENT)
async def assign_note_collection(
    note_id: UUID, body: NoteCollectionAssign, current_user_id: CurrentUser, db: DB
) -> None:
    collection_id: UUID | None = None
    if body.new_collection_name is not None:
        collection = await note_collection_repository.get_or_create(db, current_user_id, body.new_collection_name)
        collection_id = collection["id"]
    elif body.collection_id is not None:
        if await note_collection_repository.find_by_id(db, body.collection_id, current_user_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
        collection_id = body.collection_id

    if not await note_repository.set_collection(db, note_id, current_user_id, collection_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")


@router.delete("/{note_id}/collection-suggestion", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_collection_suggestion(note_id: UUID, current_user_id: CurrentUser, db: DB) -> None:
    if not await note_repository.clear_suggested_collection(db, note_id, current_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")


@router.get("/{note_id}/links", response_model=NoteLinkListResponse)
async def list_note_links(note_id: UUID, current_user_id: CurrentUser, db: DB) -> NoteLinkListResponse:
    if await note_repository.find_by_id(db, note_id, current_user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    records = await note_link_repository.find_by_note_id(db, note_id, current_user_id)
    return NoteLinkListResponse(
        links=[
            NoteLinkResponse(
                id=r["id"],
                status=r["status"],
                similarity=r["similarity"],
                note=LinkedNote(
                    id=r["note_id"],
                    topic=r["topic"],
                    summary=r["summary"],
                    collection_id=r["collection_id"],
                    collection_name=r["collection_name"],
                ),
            )
            for r in records
        ]
    )


@router.put("/{note_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_note_link(
    note_id: UUID, link_id: UUID, body: NoteLinkUpdate, current_user_id: CurrentUser, db: DB
) -> None:
    if not await note_link_repository.set_status(db, link_id, note_id, current_user_id, body.status):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
