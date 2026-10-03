import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

import asyncpg
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from core.database import get_pool
from graph.llm import llm_structured
from graph.output_schemas import SynthesisConnectionDraft, SynthesisContradictionDraft, SynthesisDraftOutput
from graph.prompts.synthesis import SYNTHESIS_PROMPT_FINGERPRINT, build_synthesis_draft_prompt
from graph.state import SynthesisConnectionState
from observability.langfuse_tracing import traced_synthesis
from repositories import collection_synthesis_repository, note_collection_repository, note_repository

MIN_SYNTHESIS_NOTES = 2
MAX_SYNTHESIS_NOTES = 30
MAX_CONNECTIONS = 5
MAX_GAPS = 5
DIALOGUE_CONNECTIONS = 3

_CITATION = re.compile(r"\[(N\d+)\]")


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


def dialogue_connections(connections: Sequence[dict[str, Any]]) -> list[SynthesisConnectionState]:
    return [
        SynthesisConnectionState(id=c["id"], title=c["title"], explanation=c["explanation"], question=c["question"])
        for c in connections[:DIALOGUE_CONNECTIONS]
    ]


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


class CollectionNotFoundError(Exception):
    pass


class NoteCountError(Exception):
    pass


class SynthesisGenerationError(Exception):
    pass


def label_notes(notes: Sequence[SourceNote]) -> dict[str, SourceNote]:
    return {f"N{i}": note for i, note in enumerate(notes, start=1)}


def build_notes_block(labeled: dict[str, SourceNote]) -> str:
    sections = []
    for label, note in labeled.items():
        section = f"### [{label}] {note.topic}\n{note.content}"
        if note.revisions:
            section += "\n\n#### 復習で深まった点\n" + "\n".join(note.revisions)
        sections.append(section)
    return "\n\n".join(sections)


def render_citations(content: str, labeled: dict[str, SourceNote]) -> str:
    def _replace(match: re.Match[str]) -> str:
        note = labeled.get(match.group(1))
        if note is None:
            return ""
        text = note.topic.replace("[", "［").replace("]", "］")
        return f"[{text}](/notes/{note.id})"

    return _CITATION.sub(_replace, content)


def _resolve(labels: Sequence[str], labeled: dict[str, SourceNote]) -> list[str]:
    note_ids: list[str] = []
    for label in labels:
        note = labeled.get(label.strip().strip("[]"))
        if note is not None and str(note.id) not in note_ids:
            note_ids.append(str(note.id))
    return note_ids


def build_connections(
    drafts: Sequence[SynthesisConnectionDraft], labeled: dict[str, SourceNote]
) -> list[dict[str, Any]]:
    connections: list[dict[str, Any]] = []
    for draft in drafts:
        note_ids = _resolve(draft.note_labels, labeled)
        if len(note_ids) < 2 or not draft.title.strip() or not draft.question.strip():
            continue
        connections.append(
            {
                "id": f"c{len(connections) + 1}",
                "title": draft.title.strip(),
                "note_ids": note_ids,
                "explanation": draft.explanation.strip(),
                "question": draft.question.strip(),
            }
        )
        if len(connections) == MAX_CONNECTIONS:
            break
    return connections


def build_contradictions(
    drafts: Sequence[SynthesisContradictionDraft], labeled: dict[str, SourceNote]
) -> list[dict[str, Any]]:
    contradictions: list[dict[str, Any]] = []
    for draft in drafts:
        note_ids = _resolve(draft.note_labels, labeled)
        if note_ids and draft.description.strip():
            contradictions.append({"note_ids": note_ids, "description": draft.description.strip()})
    return contradictions


async def generate_synthesis(collection_id: UUID, user_id: str) -> dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        collection = await note_collection_repository.find_by_id(conn, collection_id, user_id)
        if collection is None:
            raise CollectionNotFoundError
        notes = to_source_notes(await note_repository.find_contents_by_collection_id(conn, collection_id, user_id))
    if not MIN_SYNTHESIS_NOTES <= len(notes) <= MAX_SYNTHESIS_NOTES:
        raise NoteCountError

    labeled = label_notes(notes)
    prompt = build_synthesis_draft_prompt(collection_name=collection["name"], notes_block=build_notes_block(labeled))
    runnable = llm_structured.with_structured_output(SynthesisDraftOutput)
    async with traced_synthesis(user_id=user_id, collection_id=collection_id, note_count=len(notes)) as run:
        try:
            result: Any = await runnable.ainvoke(
                [SystemMessage(content=prompt)],
                config=cast(
                    RunnableConfig, {**run.config, "metadata": {"prompt_fingerprint": SYNTHESIS_PROMPT_FINGERPRINT}}
                ),
            )
        except Exception as exc:
            raise SynthesisGenerationError from exc
        if not isinstance(result, SynthesisDraftOutput) or not result.content.strip():
            raise SynthesisGenerationError
        connections = build_connections(result.connections, labeled)
        run.set_output({"connections": len(connections), "contradictions": len(result.contradictions)})

    async with pool.acquire() as conn:
        try:
            return await collection_synthesis_repository.upsert(
                conn,
                collection_id=collection_id,
                content=render_citations(result.content, labeled),
                connections=connections,
                contradictions=build_contradictions(result.contradictions, labeled),
                gaps=[g.strip() for g in result.gaps if g.strip()][:MAX_GAPS],
                source_notes=snapshot(notes),
            )
        except asyncpg.ForeignKeyViolationError as exc:
            raise CollectionNotFoundError from exc
