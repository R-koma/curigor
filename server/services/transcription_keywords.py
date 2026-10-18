import asyncio
import hashlib
import logging
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from core import config
from core.database import get_pool
from graph.llm import STRUCTURED_MODELS, llm_structured
from graph.output_schemas import TranscriptionKeywordsDraft
from graph.prompts.transcription_keywords import (
    TRANSCRIPTION_KEYWORDS_PROMPT_FINGERPRINT,
    build_transcription_keywords_prompt,
)
from observability.langfuse_tracing import traced_transcription_keywords
from repositories import dialogue_session_repository

logger = logging.getLogger(__name__)

_FORBIDDEN_CHARS = ("<", ">", "\r", "\n")
_pending: set[asyncio.Task[None]] = set()
_in_flight: set[tuple[UUID, str]] = set()


@dataclass(frozen=True)
class KeywordSource:
    topic: str
    aspects: tuple[str, ...]
    context: str
    generate: bool = True

    @property
    def fingerprint(self) -> str:
        if not self.generate:
            return hashlib.sha256("\x00".join(["listed", self.topic, *self.aspects]).encode()).hexdigest()
        model = STRUCTURED_MODELS["generate-transcription-keywords"].model
        parts = [TRANSCRIPTION_KEYWORDS_PROMPT_FINGERPRINT, model, self.topic, *self.aspects, "", self.context]
        return hashlib.sha256("\x00".join(parts).encode()).hexdigest()


def keyword_source(values: Mapping[str, Any]) -> KeywordSource | None:
    topic = str(values.get("topic") or "").strip()
    if not topic:
        return None
    session_type = values.get("session_type")
    if session_type == "learning":
        depth_map = values.get("depth_map")
        if not depth_map:
            return None
        aspects = tuple(str(a["name"]) for a in depth_map.get("aspects") or [])
        return KeywordSource(topic, aspects, str(values.get("learning_goal") or ""))
    if session_type == "review":
        return KeywordSource(topic, (), str(values.get("note_summary") or ""))
    if session_type == "explore":
        terms = tuple(str(t["term"]) for t in reversed(values.get("explore_terms") or []))
        return KeywordSource(topic, terms, "", generate=False)
    return None


def sanitize_keywords(terms: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in terms:
        term = raw.strip()
        if not term or len(term) > config.MAX_TRANSCRIPTION_KEYWORD_CHARS:
            continue
        if any(char in term for char in _FORBIDDEN_CHARS):
            continue
        key = unicodedata.normalize("NFKC", term).casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(term)
    return result[: config.MAX_TRANSCRIPTION_KEYWORDS]


def merge_keywords(source: KeywordSource, terms: Iterable[str]) -> list[str]:
    return sanitize_keywords([source.topic, *source.aspects, *terms])


def fallback_keywords(topic: str | None) -> list[str] | None:
    if not topic:
        return None
    return sanitize_keywords([topic]) or None


async def generate_terms(source: KeywordSource, run_config: dict[str, Any] | None = None) -> list[str]:
    prompt = build_transcription_keywords_prompt(topic=source.topic, aspects=source.aspects, context=source.context)
    runnable = llm_structured.with_structured_output(
        TranscriptionKeywordsDraft, task="generate-transcription-keywords"
    )
    invoke_config: RunnableConfig = {
        "run_name": "generate-transcription-keywords",
        "metadata": {"prompt_fingerprint": TRANSCRIPTION_KEYWORDS_PROMPT_FINGERPRINT},
    }
    if run_config and "callbacks" in run_config:
        invoke_config["callbacks"] = run_config["callbacks"]
    result = await runnable.ainvoke([SystemMessage(content=prompt)], config=invoke_config)
    assert isinstance(result, TranscriptionKeywordsDraft)
    return result.terms


async def refresh_transcription_keywords(session_id: UUID, user_id: str, source: KeywordSource) -> bool:
    """出どころ（トピック・観点・補足）が前回と同じなら作り直さない。作り直したら True。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        _, stored_source = await dialogue_session_repository.find_transcription_keywords(conn, session_id, user_id)
    if stored_source == source.fingerprint:
        return False
    if not source.generate:
        async with pool.acquire() as conn:
            await dialogue_session_repository.update_transcription_keywords(
                conn, session_id, merge_keywords(source, []), source.fingerprint
            )
        return True
    async with traced_transcription_keywords(session_id=session_id, user_id=user_id, topic=source.topic) as run:
        try:
            terms = await generate_terms(source, run.config)
        except Exception:
            logger.warning("transcription keyword generation failed", exc_info=True)
            terms, fingerprint = [], ""
        else:
            fingerprint = source.fingerprint
        keywords = merge_keywords(source, terms)
        run.set_output(keywords)
    async with pool.acquire() as conn:
        await dialogue_session_repository.update_transcription_keywords(conn, session_id, keywords, fingerprint)
    return True


async def _refresh_quietly(session_id: UUID, user_id: str, source: KeywordSource) -> None:
    key = (session_id, source.fingerprint)
    try:
        await refresh_transcription_keywords(session_id, user_id, source)
    except Exception:
        logger.exception("transcription keyword refresh failed: %s", session_id)
    finally:
        _in_flight.discard(key)


def schedule_transcription_keywords(session_id: UUID, user_id: str, source: KeywordSource) -> None:
    key = (session_id, source.fingerprint)
    if key in _in_flight:
        return
    _in_flight.add(key)
    task = asyncio.create_task(_refresh_quietly(session_id, user_id, source))
    _pending.add(task)
    task.add_done_callback(_pending.discard)
