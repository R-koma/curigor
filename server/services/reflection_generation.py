import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ValidationError

from core import config
from core.database import get_pool
from graph.llm import StructuredTask, llm_structured
from graph.output_schemas import ReflectionQuizOutput, ReflectionQuizQuestion, ReflectionScriptOutput
from graph.prompts.reflection import (
    REFLECTION_QUIZ_PROMPT_FINGERPRINT,
    REFLECTION_SCRIPT_PROMPT_FINGERPRINT,
    PeriodWording,
    build_reflection_quiz_prompt,
    build_reflection_script_prompt,
    period_wording,
)
from observability.langfuse_tracing import traced_reflection
from repositories import llm_usage_repository, reflection_repository
from schemas.reflection import DayReflection, ReflectionSessionType
from services.reflection import build_day, build_week_details, content_hash, week_start_of

logger = logging.getLogger(__name__)

Period = Literal["day", "week"]
Kind = Literal["script", "quiz"]


class ReflectionEmptyError(Exception):
    pass


class ReflectionLimitError(Exception):
    pass


class ReflectionGenerationError(Exception):
    pass


_SESSION_TYPE_LABELS: dict[ReflectionSessionType, str] = {
    "learning": "説明して学ぶ",
    "explore": "インプット",
    "review": "復習",
}


def _today() -> date:
    return datetime.now(ZoneInfo(config.REVIEW_TIMEZONE)).date()


def _render_day(day: DayReflection, heading: str) -> list[str]:
    lines: list[str] = []
    for group in day.groups:
        for topic in group.topics:
            lines.append(f"{heading} {topic.topic}（{_SESSION_TYPE_LABELS[group.session_type]}）\n{topic.summary}")
            lines.extend(f"- つまずいた所: {s}" for s in topic.struggles)
            for q in topic.questions:
                answer = f" / 答え: {q.answer}" if q.answer.strip() else ""
                lines.append(f"- 疑問: {q.question}{answer}")
    return lines


def render_reflection(days: list[DayReflection], period: Period) -> str:
    if period == "day":
        return "\n".join(line for day in days for line in _render_day(day, "##"))
    lines: list[str] = []
    for day in days:
        lines.append(f"## {day.day.month}月{day.day.day}日")
        lines.extend(_render_day(day, "###"))
    return "\n".join(lines)


async def _get_or_create[T: BaseModel](
    user_id: str,
    period: Period,
    start: date,
    *,
    kind: Kind,
    operation: llm_usage_repository.LlmOperation,
    task: StructuredTask,
    schema: type[T],
    fingerprint: str,
    build_prompt: Callable[[PeriodWording, str], str],
) -> T:
    today = _today()
    if period == "week":
        start = week_start_of(start)
        wording = period_wording(period, start, current=start == week_start_of(today))
    else:
        wording = period_wording(period, start, current=start == today)
    end = start + timedelta(days=7 if period == "week" else 1)

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await reflection_repository.find_items_in_range(conn, user_id, start, end, config.REVIEW_TIMEZONE)
        days = [build_day(start, rows)] if period == "day" else build_week_details(rows)
        days = [d for d in days if d.groups]
        if not days:
            raise ReflectionEmptyError
        digest = content_hash(days, wording.label)
        cached = await reflection_repository.find_generation(conn, user_id, period, start, kind)
        if cached is not None and cached["content_hash"] == digest:
            try:
                return schema.model_validate(cached["payload"])
            except ValidationError:
                logger.warning("invalid cached reflection %s for %s %s; regenerating", kind, period, start)
        usage_id = await llm_usage_repository.reserve(
            conn, user_id, operation, config.REVIEW_TIMEZONE, config.DAILY_REFLECTION_GENERATION_LIMIT
        )
    if usage_id is None:
        raise ReflectionLimitError

    prompt = build_prompt(wording, render_reflection(days, period))
    runnable = llm_structured.with_structured_output(schema, task=task)
    async with traced_reflection(user_id=user_id, period=period, kind=kind) as run:
        try:
            result: Any = await runnable.ainvoke(
                [SystemMessage(content=prompt)],
                config=cast(RunnableConfig, {**run.config, "metadata": {"prompt_fingerprint": fingerprint}}),
            )
        except Exception as exc:
            raise ReflectionGenerationError from exc
        if not isinstance(result, schema):
            raise ReflectionGenerationError
        run.set_output(result.model_dump(mode="json"))

    async with pool.acquire() as conn:
        await reflection_repository.upsert_generation(
            conn,
            user_id=user_id,
            period=period,
            start_date=start,
            kind=kind,
            content_hash=digest,
            payload=result.model_dump(mode="json"),
        )
    return result


async def get_or_create_script(user_id: str, period: Period, start: date) -> list[str]:
    output = await _get_or_create(
        user_id,
        period,
        start,
        kind="script",
        operation="reflection_script",
        task="generate-reflection-script",
        schema=ReflectionScriptOutput,
        fingerprint=REFLECTION_SCRIPT_PROMPT_FINGERPRINT,
        build_prompt=lambda w, text: build_reflection_script_prompt(
            wording=w, reflection=text, max_chars=config.MAX_SPEECH_CHARS
        ),
    )
    return output.sentences


async def get_or_create_quiz(user_id: str, period: Period, start: date) -> list[ReflectionQuizQuestion]:
    output = await _get_or_create(
        user_id,
        period,
        start,
        kind="quiz",
        operation="reflection_quiz",
        task="generate-reflection-quiz",
        schema=ReflectionQuizOutput,
        fingerprint=REFLECTION_QUIZ_PROMPT_FINGERPRINT,
        build_prompt=lambda w, text: build_reflection_quiz_prompt(wording=w, reflection=text),
    )
    return output.questions
