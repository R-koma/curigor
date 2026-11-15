import argparse
from collections.abc import Iterator

import pytest

from evals.model_override import (
    EVAL_FULL_TASKS,
    EVAL_PINNED_TASKS,
    FEEDBACK_EVAL_TASKS,
    REVIEW_END_TASKS,
    add_model_argument,
    apply_overrides,
    models_meta,
    parse_override,
    uncalled_overrides,
)
from graph.llm import RESPONSE_MODELS, STRUCTURED_MODELS, ModelSpec


@pytest.fixture
def restore_models() -> Iterator[None]:
    response, structured = dict(RESPONSE_MODELS), dict(STRUCTURED_MODELS)
    yield
    RESPONSE_MODELS.clear()
    RESPONSE_MODELS.update(response)
    STRUCTURED_MODELS.clear()
    STRUCTURED_MODELS.update(structured)


def test_parse_openai_defaults(restore_models: None) -> None:
    task, spec = parse_override("map-turn-analysis=openai:gpt-x")

    assert task == "map-turn-analysis"
    assert spec == ModelSpec(
        "openai", "gpt-x", reasoning_effort="none", temperature=STRUCTURED_MODELS["map-turn-analysis"].temperature
    )


def test_parse_response_task_inherits_its_temperature(restore_models: None) -> None:
    assert parse_override("learning-dialogue=openai:gpt-x")[1].temperature == 0.7


def test_parse_effort_drops_temperature(restore_models: None) -> None:
    assert parse_override("map-turn-analysis=openai:gpt-x:effort=high")[1] == ModelSpec(
        "openai", "gpt-x", "high", None
    )


def test_parse_anthropic_defaults(restore_models: None) -> None:
    assert parse_override("learning-dialogue=anthropic:claude-x")[1] == ModelSpec("anthropic", "claude-x", None, None)


def test_parse_explicit_temperature(restore_models: None) -> None:
    assert parse_override("learning-dialogue=anthropic:claude-x:temperature=0.3")[1].temperature == 0.3


@pytest.mark.parametrize(
    "value",
    [
        "no-such-task=openai:m",
        "learning-dialogue=azure:m",
        "learning-dialogue=openai",
        "learning-dialogue",
        "learning-dialogue=openai:m:speed=fast",
        "learning-dialogue=openai:m:temperature=hot",
    ],
)
def test_parse_rejects(value: str, restore_models: None) -> None:
    with pytest.raises(ValueError, match="learning-dialogue|no-such-task"):
        parse_override(value)


def test_apply_replaces_only_named_task(restore_models: None) -> None:
    before = dict(STRUCTURED_MODELS)

    assert apply_overrides(["map-turn-analysis=openai:gpt-x:effort=low"], EVAL_FULL_TASKS) == ["map-turn-analysis"]

    assert STRUCTURED_MODELS["map-turn-analysis"].model == "gpt-x"
    assert {k: v for k, v in STRUCTURED_MODELS.items() if k != "map-turn-analysis"} == {
        k: v for k, v in before.items() if k != "map-turn-analysis"
    }


def test_apply_rejects_task_the_eval_does_not_call(restore_models: None) -> None:
    with pytest.raises(ValueError, match="review-turn-analysis"):
        apply_overrides(["review-turn-analysis=openai:gpt-x"], EVAL_FULL_TASKS)


def test_apply_changes_nothing_when_any_value_is_invalid(restore_models: None) -> None:
    before = (dict(RESPONSE_MODELS), dict(STRUCTURED_MODELS))

    with pytest.raises(ValueError):
        apply_overrides(["learning-dialogue=openai:gpt-x", "bad"], EVAL_FULL_TASKS)

    assert (dict(RESPONSE_MODELS), dict(STRUCTURED_MODELS)) == before


def test_apply_rejects_duplicate_task(restore_models: None) -> None:
    with pytest.raises(ValueError, match="learning-dialogue"):
        apply_overrides(["learning-dialogue=openai:a", "learning-dialogue=openai:b"], EVAL_FULL_TASKS)


def test_apply_none_is_noop(restore_models: None) -> None:
    assert apply_overrides(None, EVAL_FULL_TASKS) == []


def test_models_meta_lists_full_spec(restore_models: None) -> None:
    assert models_meta(EVAL_PINNED_TASKS) == {
        "learning-dialogue": {
            "provider": "openai",
            "model": "gpt-6-luna",
            "reasoning_effort": "none",
            "temperature": 0.7,
        }
    }


def test_models_meta_is_sorted_by_task(restore_models: None) -> None:
    assert list(models_meta(EVAL_FULL_TASKS)) == sorted(EVAL_FULL_TASKS)


def test_uncalled_overrides() -> None:
    usage = {"tasks": {"learning-dialogue": {"calls": 3}}}

    assert uncalled_overrides(["learning-dialogue", "turn-analysis"], usage) == ["turn-analysis"]


def test_task_sets_are_real_tasks() -> None:
    known = set(RESPONSE_MODELS) | set(STRUCTURED_MODELS)

    assert EVAL_FULL_TASKS | EVAL_PINNED_TASKS | FEEDBACK_EVAL_TASKS | REVIEW_END_TASKS <= known


def test_add_model_argument_collects_repeated_values() -> None:
    parser = argparse.ArgumentParser()
    add_model_argument(parser)

    assert parser.parse_args(["--model", "a=b:c", "--model", "d=e:f"]).model == ["a=b:c", "d=e:f"]
    assert parser.parse_args([]).model is None
