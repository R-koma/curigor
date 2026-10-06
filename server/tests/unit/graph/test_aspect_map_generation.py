from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage

from graph.nodes._aspect_map_generation import conversation_text_for_aspect_map, generate_aspect_map
from graph.output_schemas import AspectMap, AspectNode

NOTE_ID = UUID("00000000-0000-0000-0000-000000000001")
GENERATED = AspectMap(root="二分探索", aspects=[AspectNode(name="計算量", summary="s", coverage="covered")])


def _patched_llm(ainvoke: AsyncMock) -> MagicMock:
    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=AsyncMock(ainvoke=ainvoke))
    return llm


async def test_returns_the_generated_aspect_map() -> None:
    ainvoke = AsyncMock(return_value=GENERATED)
    with patch("graph.nodes._aspect_map_generation.llm_structured", _patched_llm(ainvoke)):
        assert await generate_aspect_map("ユーザー: 半分に絞る\n", NOTE_ID) == GENERATED

    assert ainvoke.call_args.kwargs["config"] == {"run_name": "generate-aspect-map"}


async def test_returns_none_when_the_llm_raises() -> None:
    with patch("graph.nodes._aspect_map_generation.llm_structured", _patched_llm(AsyncMock(side_effect=RuntimeError))):
        assert await generate_aspect_map("x", NOTE_ID) is None


async def test_returns_none_for_an_unexpected_type() -> None:
    with patch("graph.nodes._aspect_map_generation.llm_structured", _patched_llm(AsyncMock(return_value={"a": 1}))):
        assert await generate_aspect_map("x", NOTE_ID) is None


def test_conversation_text_labels_each_speaker() -> None:
    text = conversation_text_for_aspect_map([HumanMessage(content="問い"), AIMessage(content="答え")])
    assert text == "ユーザー: 問い\nアシスタント: 答え\n"
