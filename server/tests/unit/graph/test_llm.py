from typing import get_args
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from graph.llm import (
    RESPONSE_MODELS,
    STRUCTURED_MODELS,
    ModelSpec,
    ResponseTask,
    StructuredTask,
    build_chat_model,
    llm,
    llm_structured,
)

_CLAUDE = ModelSpec(provider="anthropic", model="claude-sonnet-5-5", reasoning_effort="low")


class _Schema(BaseModel):
    value: str


def test_every_task_has_a_model() -> None:
    assert set(RESPONSE_MODELS) == set(get_args(ResponseTask))
    assert set(STRUCTURED_MODELS) == set(get_args(StructuredTask))


def test_default_models_match_the_previous_two_clients() -> None:
    assert set(RESPONSE_MODELS.values()) == {
        ModelSpec(provider="openai", model="gpt-6-luna", reasoning_effort="none", temperature=0.7)
    }
    assert set(STRUCTURED_MODELS.values()) == {
        ModelSpec(provider="openai", model="gpt-6-luna", reasoning_effort="none", temperature=0)
    }


def test_openai_client_receives_model_effort_and_temperature() -> None:
    model = build_chat_model(RESPONSE_MODELS["learning-dialogue"])

    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "gpt-6-luna"
    assert model.reasoning_effort == "none"
    assert model.temperature == 0.7


def test_anthropic_client_receives_effort_and_no_temperature() -> None:
    model = build_chat_model(_CLAUDE)

    assert isinstance(model, ChatAnthropic)
    assert model.model == "claude-sonnet-5-5"
    assert model.effort == "low"
    assert model.temperature is None


async def test_response_uses_the_model_of_its_task() -> None:
    reply = AIMessage(content="質問です", id="m1")
    chat = MagicMock(ainvoke=AsyncMock(return_value=reply))
    with (
        patch.dict(RESPONSE_MODELS, {"review-dialogue": _CLAUDE}),
        patch("graph.llm.build_chat_model", MagicMock(return_value=chat)) as build,
    ):
        result = await llm.ainvoke(["hi"], {"run_name": "x"}, task="review-dialogue")

    build.assert_called_once_with(_CLAUDE)
    chat.ainvoke.assert_awaited_once_with(["hi"], {"run_name": "x"})
    assert result is reply


async def test_block_content_is_flattened_to_text_keeping_the_id() -> None:
    reply = AIMessage(
        content=[{"type": "thinking", "thinking": ""}, {"type": "text", "text": "質問です"}],
        id="m1",
    )
    chat = MagicMock(ainvoke=AsyncMock(return_value=reply))
    with patch("graph.llm.build_chat_model", MagicMock(return_value=chat)):
        result = await llm.ainvoke(["hi"], task="learning-dialogue")

    assert result.content == "質問です"
    assert result.id == "m1"


def test_structured_output_on_anthropic_uses_json_schema() -> None:
    chat = MagicMock()
    with (
        patch.dict(STRUCTURED_MODELS, {"analyze-dialogue": _CLAUDE}),
        patch("graph.llm.build_chat_model", MagicMock(return_value=chat)),
    ):
        llm_structured.with_structured_output(_Schema, task="analyze-dialogue")

    chat.with_structured_output.assert_called_once_with(_Schema, method="json_schema")


def test_structured_output_on_openai_keeps_the_default_method() -> None:
    chat = MagicMock()
    with patch("graph.llm.build_chat_model", MagicMock(return_value=chat)):
        llm_structured.with_structured_output(_Schema, task="analyze-dialogue")

    chat.with_structured_output.assert_called_once_with(_Schema)
