import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from evals import eval as eval_cli
from evals.judge import JudgeUsage
from evals.replay import Generation
from evals.runner import InstanceResult, RunResult
from graph.llm import RESPONSE_MODELS, STRUCTURED_MODELS


@pytest.fixture
def restore_models() -> Iterator[None]:
    response, structured = dict(RESPONSE_MODELS), dict(STRUCTURED_MODELS)
    yield
    RESPONSE_MODELS.clear()
    RESPONSE_MODELS.update(response)
    STRUCTURED_MODELS.clear()
    STRUCTURED_MODELS.update(structured)


def _main(*argv: str) -> None:
    with patch("sys.argv", ["evals.eval", *argv]), patch.object(eval_cli, "set_judge_cache"):
        import asyncio

        asyncio.run(eval_cli.main())


@pytest.mark.parametrize(
    "argv",
    [
        ["--mode", "scoring", "--model", "learning-dialogue=openai:m"],
        ["--rescore-report", "x.json", "--model", "learning-dialogue=openai:m"],
    ],
)
def test_model_requires_generation(argv: list[str], restore_models: None) -> None:
    before = (dict(RESPONSE_MODELS), dict(STRUCTURED_MODELS))

    with pytest.raises(SystemExit, match="--model"):
        _main(*argv)

    assert (dict(RESPONSE_MODELS), dict(STRUCTURED_MODELS)) == before


def test_pinned_rejects_analysis_override(restore_models: None) -> None:
    with pytest.raises(SystemExit, match="map-turn-analysis"):
        _main("--mode", "regression", "--replay-mode", "pinned", "--model", "map-turn-analysis=openai:m")


def test_invalid_model_value_exits_with_the_message(restore_models: None) -> None:
    with pytest.raises(SystemExit, match="bad"):
        _main("--mode", "regression", "--model", "bad")


def _result_calling(*tasks: str) -> InstanceResult:
    calls = [
        {
            "task": task,
            "model": "gpt-6-luna",
            "input_tokens": 1,
            "cached_input_tokens": 0,
            "output_tokens": 1,
            "reasoning_tokens": 0,
            "seconds": 0.1,
        }
        for task in tasks
    ]
    generation = Generation(output="x", turn_analysis=None, covered_aspects=[], turn_count=1, usage=calls)
    return InstanceResult("fm", "t1", None, [RunResult(run_index=1, output="x", outcomes=[], generation=generation)])


async def test_override_of_uncalled_task_fails_after_writing_report(tmp_path: Path, restore_models: None) -> None:
    out = tmp_path / "report.json"
    outcome: tuple[Any, ...] = ([_result_calling("learning-dialogue")], [], {}, JudgeUsage(), [])
    argv = [
        "evals.eval",
        "--mode",
        "regression",
        "--no-cascade",
        "--out",
        str(out),
        "--checkpoint-dir",
        str(tmp_path / "ck"),
        "--model",
        "turn-analysis=openai:gpt-x",
    ]

    with (
        patch("sys.argv", argv),
        patch.object(eval_cli, "set_judge_cache"),
        patch.object(eval_cli, "run", AsyncMock(return_value=outcome)),
        pytest.raises(SystemExit, match="turn-analysis"),
    ):
        await eval_cli.main()

    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["meta"]["models"]["turn-analysis"]["model"] == "gpt-x"
    assert list(report["usage"]["tasks"]) == ["learning-dialogue"]


async def test_override_of_called_task_succeeds(tmp_path: Path, restore_models: None) -> None:
    out = tmp_path / "report.json"
    outcome: tuple[Any, ...] = ([_result_calling("learning-dialogue")], [], {}, JudgeUsage(), [])
    argv = ["evals.eval", "--mode", "regression", "--no-cascade", "--out", str(out)]
    argv += ["--checkpoint-dir", str(tmp_path / "ck"), "--model", "learning-dialogue=openai:gpt-x"]

    with (
        patch("sys.argv", argv),
        patch.object(eval_cli, "set_judge_cache"),
        patch.object(eval_cli, "run", AsyncMock(return_value=outcome)),
    ):
        await eval_cli.main()

    assert json.loads(out.read_text(encoding="utf-8"))["meta"]["models"]["learning-dialogue"]["model"] == "gpt-x"


async def test_rescore_carries_over_usage_and_models(tmp_path: Path, restore_models: None) -> None:
    source = tmp_path / "source.json"
    task_stats = {
        "model": "orig",
        "calls": 9,
        "cost_per_call_usd": 0.1,
        "seconds_p50": 1.0,
        "seconds_p95": 2.0,
    }
    source_usage = {"tasks": {"learning-dialogue": task_stats}, "estimated_cost_usd": 1.0, "unpriced_models": []}
    source_models = {"learning-dialogue": {"model": "orig"}}
    source.write_text(
        json.dumps(
            {
                "meta": {
                    "mode": "regression",
                    "runs": 1,
                    "replay_mode": "full",
                    "route": "all",
                    "traces": None,
                    "model": "orig",
                    "temperature": 0.7,
                    "prompt_version": "v",
                    "prompt_fingerprint": "p",
                    "map_prompt_fingerprint": "m",
                    "models": source_models,
                },
                "records": [],
                "usage": source_usage,
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out.json"
    outcome: tuple[Any, ...] = ([], [], {}, JudgeUsage(), [])

    with (
        patch("sys.argv", ["evals.eval", "--rescore-report", str(source), "--no-cascade", "--out", str(out)]),
        patch.object(eval_cli, "set_judge_cache"),
        patch.object(eval_cli, "run", AsyncMock(return_value=outcome)),
    ):
        await eval_cli.main()

    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["usage"] == source_usage
    assert report["meta"]["models"] == source_models


async def test_rescore_of_an_old_report_has_no_usage_or_models(tmp_path: Path, restore_models: None) -> None:
    source = tmp_path / "source.json"
    meta = {
        "mode": "regression",
        "runs": 1,
        "replay_mode": "full",
        "route": "all",
        "traces": None,
        "model": "orig",
        "temperature": 0.7,
        "prompt_version": "v",
        "prompt_fingerprint": "p",
        "map_prompt_fingerprint": "m",
    }
    source.write_text(json.dumps({"meta": meta, "records": []}), encoding="utf-8")
    out = tmp_path / "out.json"

    with (
        patch("sys.argv", ["evals.eval", "--rescore-report", str(source), "--no-cascade", "--out", str(out)]),
        patch.object(eval_cli, "set_judge_cache"),
        patch.object(eval_cli, "run", AsyncMock(return_value=([], [], {}, JudgeUsage(), []))),
    ):
        await eval_cli.main()

    report = json.loads(out.read_text(encoding="utf-8"))
    assert "usage" not in report
    assert "models" not in report["meta"]
