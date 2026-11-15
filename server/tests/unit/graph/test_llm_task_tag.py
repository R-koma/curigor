from collections.abc import Iterator

import pytest
from langchain_core.messages import HumanMessage

from graph import llm as llm_module
from graph.llm import INTERNAL_LLM_TAG, llm, llm_structured
from tests.unit.fake_chat_model import FakeChatModel


@pytest.fixture
def fake_model(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeChatModel]:
    model = FakeChatModel(seen_tags=[])
    monkeypatch.setattr(llm_module, "build_chat_model", lambda spec: model)
    yield model


async def test_response_call_carries_task_tag(fake_model: FakeChatModel) -> None:
    await llm.ainvoke([HumanMessage("x")], task="learning-dialogue")

    assert "llm-task:learning-dialogue" in fake_model.seen_tags[-1]


async def test_response_call_keeps_caller_tags(fake_model: FakeChatModel) -> None:
    await llm.ainvoke([HumanMessage("x")], {"tags": ["a"]}, task="learning-dialogue")

    assert {"a", "llm-task:learning-dialogue"} <= set(fake_model.seen_tags[-1])


async def test_stream_carries_task_tag(fake_model: FakeChatModel) -> None:
    _ = [chunk async for chunk in llm.astream([HumanMessage("x")], task="explore-dialogue")]

    assert "llm-task:explore-dialogue" in fake_model.seen_tags[-1]


async def test_structured_call_keeps_internal_tag(fake_model: FakeChatModel) -> None:
    runnable = llm_structured.with_structured_output(dict, task="map-turn-analysis").with_config(
        tags=[INTERNAL_LLM_TAG]
    )

    await runnable.ainvoke([HumanMessage("x")])

    assert {INTERNAL_LLM_TAG, "llm-task:map-turn-analysis"} <= set(fake_model.seen_tags[-1])
