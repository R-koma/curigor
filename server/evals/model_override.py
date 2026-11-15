import argparse
from collections.abc import Iterable, Sequence
from dataclasses import asdict
from typing import Any, cast, get_args

from evals.tools.capture_feedback import FEEDBACK_TASKS
from graph.llm import RESPONSE_MODELS, STRUCTURED_MODELS, ModelSpec, Provider

EVAL_FULL_TASKS: frozenset[str] = frozenset({"turn-analysis", "map-turn-analysis", "learning-dialogue"})
EVAL_PINNED_TASKS: frozenset[str] = frozenset({"learning-dialogue"})
FEEDBACK_EVAL_TASKS: frozenset[str] = frozenset(FEEDBACK_TASKS)
REVIEW_END_TASKS: frozenset[str] = frozenset({"review-turn-analysis"})

_FORMAT = "<task>=<provider>:<model>[:effort=<値>][:temperature=<数>]"


def add_model_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--model",
        action="append",
        dest="model",
        metavar="TASK=PROVIDER:MODEL[:effort=E][:temperature=T]",
        help="タスクのモデルを上書きして生成する（複数回指定できる）",
    )


def _models_of(task: str) -> dict[Any, ModelSpec]:
    return cast(dict[Any, ModelSpec], RESPONSE_MODELS if task in RESPONSE_MODELS else STRUCTURED_MODELS)


def _task_list(tasks: Iterable[str]) -> str:
    return "、".join(sorted(tasks))


def parse_override(value: str) -> tuple[str, ModelSpec]:
    task, separator, rest = value.partition("=")
    known = {*RESPONSE_MODELS, *STRUCTURED_MODELS}
    if not separator or task not in known:
        raise ValueError(f"--model の指定が誤っている: {value!r}（形は {_FORMAT}。タスク名: {_task_list(known)}）")
    parts = rest.split(":")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError(f"--model の指定が誤っている: {value!r}（形は {_FORMAT}）")
    provider, model, *options = parts
    if provider not in get_args(Provider):
        raise ValueError(f"--model の提供元が誤っている: {value!r}（{_task_list(get_args(Provider))} のどちらか）")

    effort: str | None = "none" if provider == "openai" else None
    temperature: float | None = None
    explicit_temperature = False
    for option in options:
        key, _, option_value = option.partition("=")
        if key == "effort" and option_value:
            effort = option_value
        elif key == "temperature":
            try:
                temperature = float(option_value)
            except ValueError:
                raise ValueError(f"--model の temperature が数でない: {value!r}") from None
            explicit_temperature = True
        else:
            raise ValueError(f"--model のオプションが誤っている: {value!r}（使えるのは effort= と temperature=）")
    if not explicit_temperature and provider == "openai" and effort == "none":
        temperature = _models_of(task)[task].temperature
    return task, ModelSpec(cast(Provider, provider), model, effort, temperature)


def apply_overrides(values: Sequence[str] | None, allowed: frozenset[str]) -> list[str]:
    parsed = [parse_override(value) for value in values or []]
    tasks = [task for task, _ in parsed]
    for task in tasks:
        if tasks.count(task) > 1:
            raise ValueError(f"--model で同じタスクを 2 回指定している: {task}")
        if task not in allowed:
            raise ValueError(f"{task} はこの eval が呼ばないタスク（上書きできるのは {_task_list(allowed)}）")
    for task, spec in parsed:
        _models_of(task)[task] = spec
    return tasks


def models_meta(tasks: Iterable[str]) -> dict[str, dict[str, Any]]:
    return {task: asdict(_models_of(task)[task]) for task in sorted(tasks)}


def uncalled_overrides(overridden: Sequence[str], usage: dict[str, Any]) -> list[str]:
    return [task for task in overridden if not usage["tasks"].get(task, {}).get("calls")]
