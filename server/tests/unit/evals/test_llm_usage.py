from collections.abc import Iterator
from typing import Any

import pytest
from langchain_core.messages import HumanMessage

from evals import pricing
from evals.llm_usage import current_recorder, print_usage, record_usage, summarize_usage
from evals.pricing import Price
from graph import llm as llm_module
from graph.llm import llm, llm_structured
from tests.unit.fake_chat_model import FakeChatModel


@pytest.fixture
def fake_model(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeChatModel]:
    model = FakeChatModel(seen_tags=[])
    monkeypatch.setattr(llm_module, "build_chat_model", lambda spec: model)
    yield model


def _call(task: str, model: str, input_tokens: int, cached: int, output_tokens: int, seconds: float) -> dict[str, Any]:
    return {
        "task": task,
        "model": model,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached,
        "output_tokens": output_tokens,
        "reasoning_tokens": 0,
        "seconds": seconds,
    }


async def test_recorder_collects_task_tokens_and_time(fake_model: FakeChatModel) -> None:
    with record_usage() as recorder:
        await llm.ainvoke([HumanMessage("x")], task="learning-dialogue")

    (call,) = recorder.calls
    assert call["task"] == "learning-dialogue"
    assert call["model"] == "gpt-6-luna"
    assert (call["input_tokens"], call["cached_input_tokens"]) == (100, 40)
    assert (call["output_tokens"], call["reasoning_tokens"]) == (30, 10)
    assert call["seconds"] >= 0


async def test_recorder_collects_structured_calls(fake_model: FakeChatModel) -> None:
    with record_usage() as recorder:
        await llm_structured.with_structured_output(dict, task="map-turn-analysis").ainvoke([HumanMessage("x")])

    assert [call["task"] for call in recorder.calls] == ["map-turn-analysis"]


async def test_nothing_recorded_outside_the_block(fake_model: FakeChatModel) -> None:
    with record_usage() as recorder:
        pass
    await llm.ainvoke([HumanMessage("x")], task="learning-dialogue")

    assert recorder.calls == []
    assert current_recorder() is None


async def test_failed_call_is_not_recorded(fake_model: FakeChatModel) -> None:
    fake_model.fail = True

    with record_usage() as recorder, pytest.raises(RuntimeError):
        await llm.ainvoke([HumanMessage("x")], task="learning-dialogue")

    assert recorder.calls == []


async def test_current_recorder_is_the_active_one() -> None:
    with record_usage() as recorder:
        assert current_recorder() is recorder


def test_summarize_groups_by_task_and_prices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pricing, "PRICE_PER_MTOK", {"m": Price(1.0, 0.1, 2.0)})
    calls = [_call("a", "m", 1_000_000, 0, 0, seconds=s) for s in (1.0, 2.0, 9.0)] + [
        _call("b", "zzz", 1, 0, 1, seconds=1.0)
    ]

    usage = summarize_usage(calls)

    assert usage["tasks"]["a"]["calls"] == 3
    assert usage["tasks"]["a"]["estimated_cost_usd"] == pytest.approx(3.0)
    assert usage["tasks"]["a"]["cost_per_call_usd"] == pytest.approx(1.0)
    assert (usage["tasks"]["a"]["seconds_p50"], usage["tasks"]["a"]["seconds_p95"]) == (2.0, 9.0)
    assert usage["tasks"]["b"]["estimated_cost_usd"] is None
    assert usage["tasks"]["b"]["cost_per_call_usd"] is None
    assert usage["estimated_cost_usd"] is None
    assert usage["unpriced_models"] == ["zzz"]


def test_summarize_empty() -> None:
    assert summarize_usage([]) == {"tasks": {}, "estimated_cost_usd": 0.0, "unpriced_models": []}


def test_print_usage_warns_about_unpriced_models(capsys: pytest.CaptureFixture[str]) -> None:
    print_usage(summarize_usage([_call("b", "zzz", 1, 0, 1, seconds=1.0)]))

    out = capsys.readouterr().out
    assert "b" in out and "料金表に無いモデル" in out and "zzz" in out
