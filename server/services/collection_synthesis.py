import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class SourceNote:
    id: UUID
    topic: str
    content: str
    revisions: tuple[str, ...]


@dataclass(frozen=True)
class Staleness:
    is_stale: bool
    changed_note_ids: list[str]


def to_source_notes(rows: Sequence[dict[str, Any]]) -> list[SourceNote]:
    return [
        SourceNote(id=r["id"], topic=r["topic"], content=r["content"], revisions=tuple(r["revisions"])) for r in rows
    ]


def note_content_hash(note: SourceNote) -> str:
    return hashlib.sha256("\x00".join([note.content, *note.revisions]).encode()).hexdigest()


def snapshot(notes: Sequence[SourceNote]) -> list[dict[str, str]]:
    return [{"note_id": str(n.id), "content_hash": note_content_hash(n)} for n in notes]


def staleness(source_notes: Sequence[dict[str, str]], current: Sequence[SourceNote]) -> Staleness:
    recorded = {s["note_id"]: s["content_hash"] for s in source_notes}
    hashes = {str(n.id): note_content_hash(n) for n in current}
    changed = [note_id for note_id, content_hash in hashes.items() if recorded.get(note_id) != content_hash]
    removed = recorded.keys() - hashes.keys()
    return Staleness(is_stale=bool(changed or removed), changed_note_ids=changed)
