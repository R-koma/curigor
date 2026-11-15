from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from langchain_core.callbacks import BaseCallbackHandler
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


class _RunTags(BaseCallbackHandler):
    def __init__(self) -> None:
        self.root_chain_tags: list[list[str]] = []
        self.llm_tags: list[list[str]] = []

    def on_chain_start(
        self,
        serialized: Any,
        inputs: Any,
        *,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        if parent_run_id is None:
            self.root_chain_tags.append(list(tags or []))

    def on_chat_model_start(
        self, serialized: Any, messages: Any, *, tags: list[str] | None = None, **kwargs: Any
    ) -> None:
        self.llm_tags.append(list(tags or []))


async def test_task_tag_stays_off_the_root_chain_of_a_structured_call(fake_model: FakeChatModel) -> None:
    handler = _RunTags()
    runnable = llm_structured.with_structured_output(dict, task="generate-collection-synthesis")

    await runnable.ainvoke([HumanMessage("x")], config={"callbacks": [handler]})

    assert not any(tag.startswith("llm-task:") for tags in handler.root_chain_tags for tag in tags)
    assert "llm-task:generate-collection-synthesis" in handler.llm_tags[-1]


async def test_internal_tag_and_task_tag_are_both_on_the_llm_run(fake_model: FakeChatModel) -> None:
    handler = _RunTags()
    runnable = llm_structured.with_structured_output(dict, task="map-turn-analysis").with_config(
        tags=[INTERNAL_LLM_TAG]
    )

    await runnable.ainvoke([HumanMessage("x")], config={"callbacks": [handler]})

    assert {INTERNAL_LLM_TAG, "llm-task:map-turn-analysis"} <= set(handler.llm_tags[-1])


async def test_response_call_passes_the_caller_config_unchanged(fake_model: FakeChatModel) -> None:
    handler = _RunTags()

    await llm.ainvoke([HumanMessage("x")], {"callbacks": [handler], "tags": ["a"]}, task="learning-dialogue")

    assert not any(tag.startswith("llm-task:") for tags in handler.root_chain_tags for tag in tags)
    assert {"a", "llm-task:learning-dialogue"} <= set(handler.llm_tags[-1])
