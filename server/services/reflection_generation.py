from collections.abc import Callable
from datetime import date, timedelta
from typing import Any, Literal, cast

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from core import config
from core.database import get_pool
from graph.llm import StructuredTask, llm_structured
from graph.output_schemas import ReflectionScriptOutput
from graph.prompts.reflection import (
    REFLECTION_SCRIPT_PROMPT_FINGERPRINT,
    build_reflection_script_prompt,
)
from observability.langfuse_tracing import traced_reflection
from repositories import llm_usage_repository, reflection_repository
from schemas.reflection import DayReflection, WeekReflection
from services.reflection import build_day, build_week, content_hash, week_start_of

Period = Literal["day", "week"]
Kind = Literal["script", "quiz"]


class ReflectionEmptyError(Exception):
    pass


class ReflectionLimitError(Exception):
    pass


class ReflectionGenerationError(Exception):
    pass


def render_reflection(reflection: DayReflection | WeekReflection) -> str:
    lines: list[str] = []
    if isinstance(reflection, DayReflection):
        for group in reflection.groups:
            for topic in group.topics:
                lines.append(f"## {topic.topic}（{group.session_type}）\n{topic.summary}")
                lines.extend(f"- つまずいた所: {s}" for s in topic.struggles)
                lines.extend(f"- 疑問: {q.question} / 答え: {q.answer}" for q in topic.questions)
        return "\n".join(lines)
    for day in reflection.days:
        lines.append(f"## {day.day.isoformat()}")
        lines.extend(f"- {t.topic}（{t.session_type}）" for t in day.topics)
    for item in reflection.struggles:
        label = "つまずいた所" if item.kind == "struggle" else "疑問"
        answer = f" / 答え: {item.answer}" if item.answer else ""
        lines.append(f"- {item.topic} の{label}: {item.text}{answer}")
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
    build_prompt: Callable[[Period, str], str],
) -> T:
    if period == "week":
        start = week_start_of(start)
    end = start + timedelta(days=7 if period == "week" else 1)

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await reflection_repository.find_items_in_range(conn, user_id, start, end, config.REVIEW_TIMEZONE)
        reflection: DayReflection | WeekReflection
        if period == "day":
            reflection = build_day(start, rows)
            is_empty = not reflection.groups
        else:
            reflection = build_week(start, rows)
            is_empty = not reflection.days
        if is_empty:
            raise ReflectionEmptyError
        digest = content_hash(reflection)
        cached = await reflection_repository.find_generation(conn, user_id, period, start, kind)
        if cached is not None and cached["content_hash"] == digest:
            return schema.model_validate(cached["payload"])
        usage_id = await llm_usage_repository.reserve(
            conn, user_id, operation, config.REVIEW_TIMEZONE, config.DAILY_REFLECTION_GENERATION_LIMIT
        )
    if usage_id is None:
        raise ReflectionLimitError

    prompt = build_prompt(period, render_reflection(reflection))
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
        build_prompt=lambda p, text: build_reflection_script_prompt(
            period=p, reflection=text, max_chars=config.MAX_SPEECH_CHARS
        ),
    )
    return output.sentences
