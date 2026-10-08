from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class LinkedNote(BaseModel):
    id: UUID
    topic: str
    summary: str | None
    collection_id: UUID | None
    collection_name: str | None


class NoteLinkResponse(BaseModel):
    id: UUID
    status: Literal["suggested", "accepted"]
    similarity: float
    note: LinkedNote


class NoteLinkListResponse(BaseModel):
    links: list[NoteLinkResponse]


class NoteLinkUpdate(BaseModel):
    status: Literal["accepted", "dismissed"]
