import math
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult
from langchain_core.tracers.context import register_configure_hook

from evals.pricing import estimate_cost
from graph.llm import LLM_TASK_TAG_PREFIX, RESPONSE_MODELS, STRUCTURED_MODELS

_UNKNOWN = "unknown"


def _task_of(tags: list[str] | None) -> str:
    for tag in tags or []:
        if tag.startswith(LLM_TASK_TAG_PREFIX):
            return tag.removeprefix(LLM_TASK_TAG_PREFIX)
    return _UNKNOWN


def _model_of(task: str, response: LLMResult) -> str:
    spec = RESPONSE_MODELS.get(task) or STRUCTURED_MODELS.get(task)  # type: ignore[call-overload]
    if spec is not None:
        return str(spec.model)
    return str((response.llm_output or {}).get("model_name") or _UNKNOWN)


class UsageRecorder(BaseCallbackHandler):
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._started: dict[UUID, tuple[float, str]] = {}

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self._started[run_id] = (time.perf_counter(), _task_of(tags))

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        started = self._started.pop(run_id, None)
        if started is None:
            return
        began, task = started
        message = response.generations[0][0] if response.generations and response.generations[0] else None
        usage = getattr(getattr(message, "message", None), "usage_metadata", None) or {}
        self.calls.append(
            {
                "task": task,
                "model": _model_of(task, response),
                "input_tokens": usage.get("input_tokens") or 0,
                "cached_input_tokens": (usage.get("input_token_details") or {}).get("cache_read") or 0,
                "output_tokens": usage.get("output_tokens") or 0,
                "reasoning_tokens": (usage.get("output_token_details") or {}).get("reasoning") or 0,
                "seconds": time.perf_counter() - began,
            }
        )

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._started.pop(run_id, None)


_recorder: ContextVar[UsageRecorder | None] = ContextVar("eval_usage_recorder", default=None)
register_configure_hook(_recorder, inheritable=True)


def current_recorder() -> UsageRecorder | None:
    return _recorder.get()


@contextmanager
def record_usage() -> Iterator[UsageRecorder]:
    recorder = UsageRecorder()
    token = _recorder.set(recorder)
    try:
        yield recorder
    finally:
        _recorder.reset(token)


def _percentile(sorted_values: list[float], fraction: float) -> float:
    return sorted_values[max(math.ceil(fraction * len(sorted_values)) - 1, 0)]


def summarize_usage(calls: Iterable[dict[str, Any]]) -> dict[str, Any]:
    by_task: dict[str, list[dict[str, Any]]] = {}
    for call in calls:
        by_task.setdefault(call["task"], []).append(call)

    tasks: dict[str, Any] = {}
    unpriced: set[str] = set()
    total: float | None = 0.0
    for task in sorted(by_task):
        task_calls = by_task[task]
        costs = [
            estimate_cost(
                call["model"],
                input_tokens=call["input_tokens"],
                output_tokens=call["output_tokens"],
                cached_input_tokens=call["cached_input_tokens"],
            )
            for call in task_calls
        ]
        unpriced.update(call["model"] for call, cost in zip(task_calls, costs, strict=True) if cost is None)
        cost = None if any(c is None for c in costs) else sum(c for c in costs if c is not None)
        seconds = sorted(call["seconds"] for call in task_calls)
        tasks[task] = {
            "model": ", ".join(sorted({call["model"] for call in task_calls})),
            "calls": len(task_calls),
            "input_tokens": sum(call["input_tokens"] for call in task_calls),
            "cached_input_tokens": sum(call["cached_input_tokens"] for call in task_calls),
            "output_tokens": sum(call["output_tokens"] for call in task_calls),
            "reasoning_tokens": sum(call["reasoning_tokens"] for call in task_calls),
            "estimated_cost_usd": cost,
            "cost_per_call_usd": None if cost is None else cost / len(task_calls),
            "seconds_p50": _percentile(seconds, 0.5),
            "seconds_p95": _percentile(seconds, 0.95),
        }
        total = None if cost is None or total is None else total + cost
    return {"tasks": tasks, "estimated_cost_usd": total, "unpriced_models": sorted(unpriced)}


def print_usage(usage: dict[str, Any]) -> None:
    for task, stats in usage["tasks"].items():
        per_call = stats["cost_per_call_usd"]
        cost = "料金不明" if per_call is None else f"${per_call:.5f}/回"
        print(
            f"  {task}: {stats['model']} {stats['calls']} 回 {cost} "
            f"p50 {stats['seconds_p50']:.1f}s p95 {stats['seconds_p95']:.1f}s"
        )
    total = usage["estimated_cost_usd"]
    print(f"  生成側の料金の見積もり合計: {'料金不明' if total is None else f'${total:.4f}'}")
    if usage["unpriced_models"]:
        print(f"  警告: 料金表に無いモデル: {', '.join(usage['unpriced_models'])}（evals/pricing.py に足す）")
