from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, StringConstraints, model_validator

MAX_COLLECTION_NAME_LENGTH = 100

CollectionName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_COLLECTION_NAME_LENGTH)
]


class CollectionCreate(BaseModel):
    name: CollectionName


class CollectionRename(BaseModel):
    name: CollectionName


class CollectionResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class CollectionSummary(CollectionResponse):
    note_count: int


class CollectionListResponse(BaseModel):
    collections: list[CollectionSummary]


class CollectionNote(BaseModel):
    id: UUID
    topic: str
    summary: str | None
    status: str
    created_at: datetime
    review_count: int
    is_established: bool


class CollectionDetailResponse(CollectionResponse):
    notes: list[CollectionNote]


class NoteCollectionAssign(BaseModel):
    collection_id: UUID | None = None
    new_collection_name: CollectionName | None = None

    @model_validator(mode="after")
    def _single_target(self) -> Self:
        if self.collection_id is not None and self.new_collection_name is not None:
            raise ValueError("Specify either collection_id or new_collection_name")
        return self


class SynthesisConnection(BaseModel):
    id: str
    title: str
    note_ids: list[UUID]
    explanation: str
    question: str


class SynthesisContradiction(BaseModel):
    note_ids: list[UUID]
    description: str


class SynthesisInsight(BaseModel):
    id: UUID
    connection_title: str
    content: str
    created_at: datetime


class SynthesisResponse(BaseModel):
    collection_id: UUID
    content: str
    connections: list[SynthesisConnection]
    contradictions: list[SynthesisContradiction]
    gaps: list[str]
    generated_at: datetime
    is_stale: bool
    changed_note_ids: list[UUID]
    insights: list[SynthesisInsight]
