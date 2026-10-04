from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from graph.output_schemas import SynthesisInsightDraft, SynthesisInsightsOutput
from graph.state import LearningState, SynthesisConnectionState

COLLECTION_ID = UUID("00000000-0000-0000-0000-0000000000c1")

CONNECTIONS: list[SynthesisConnectionState] = [
    {"id": "c1", "title": "コンテキストスイッチ", "explanation": "参考1", "question": "問い1"},
    {"id": "c2", "title": "ページング", "explanation": "参考2", "question": "問い2"},
]


def _state(messages: list[BaseMessage], **overrides: Any) -> LearningState:
    base: dict[str, Any] = {
        "user_id": "user-1",
        "dialogue_session_id": "00000000-0000-0000-0000-000000000001",
        "messages": messages,
        "topic": "Linuxのしくみ",
        "turn_count": 1,
        "should_generate_note": False,
        "session_type": "synthesis",
        "collection_id": COLLECTION_ID,
        "synthesis_notes": "### [N1] プロセス\n本文",
        "synthesis_connections": CONNECTIONS,
    }
    base.update(overrides)
    return cast(LearningState, base)


def _system_prompt(mock_llm: MagicMock) -> str:
    messages = mock_llm.ainvoke.call_args.args[0]
    return str(messages[0].content)


class TestCurrentConnectionIndex:
    def test_first_answer_is_about_the_first_connection(self) -> None:
        from graph.nodes.synthesis import current_connection_index

        messages = [HumanMessage("Linuxのしくみ"), AIMessage("問い1"), HumanMessage("答え1")]

        assert current_connection_index(messages) == 0

    def test_second_answer_is_about_the_second_connection(self) -> None:
        from graph.nodes.synthesis import current_connection_index

        messages = [
            HumanMessage("Linuxのしくみ"),
            AIMessage("問い1"),
            HumanMessage("答え1"),
            AIMessage("問い2"),
            HumanMessage("答え2"),
        ]

        assert current_connection_index(messages) == 1


class TestSynthesisStart:
    async def test_asks_the_first_connection(self) -> None:
        with patch("graph.nodes.synthesis.llm") as mock_llm:
            mock_llm.ainvoke = AsyncMock(return_value=AIMessage("問い1を聞く"))
            from graph.nodes.synthesis import synthesis_start

            result = await synthesis_start(_state([]))

        assert "問い1" in _system_prompt(mock_llm)
        assert "参考1" not in _system_prompt(mock_llm)
        assert [m.content for m in result["messages"]] == ["Linuxのしくみ", "問い1を聞く"]
        assert result["should_generate_note"] is False


class TestSynthesisDialogue:
    async def test_checks_the_current_answer_and_asks_the_next(self) -> None:
        messages = [HumanMessage("Linuxのしくみ"), AIMessage("問い1"), HumanMessage("答え1")]
        with patch("graph.nodes.synthesis.llm") as mock_llm:
            mock_llm.ainvoke = AsyncMock(return_value=AIMessage("次へ"))
            from graph.nodes.synthesis import synthesis_dialogue

            result = await synthesis_dialogue(_state(messages, turn_count=2))

        prompt = _system_prompt(mock_llm)
        assert "参考1" in prompt
        assert "問い2" in prompt
        assert "参考2" not in prompt
        assert result["turn_count"] == 3
        assert result["should_generate_note"] is False

    async def test_after_the_last_connection_there_is_no_next_question(self) -> None:
        messages = [
            HumanMessage("Linuxのしくみ"),
            AIMessage("問い1"),
            HumanMessage("答え1"),
            AIMessage("問い2"),
            HumanMessage("答え2"),
        ]
        with patch("graph.nodes.synthesis.llm") as mock_llm:
            mock_llm.ainvoke = AsyncMock(return_value=AIMessage("おわり"))
            from graph.nodes.synthesis import synthesis_dialogue

            await synthesis_dialogue(_state(messages))

        prompt = _system_prompt(mock_llm)
        assert "参考2" in prompt
        assert "## 次に聞くつながり\nなし" in prompt

    async def test_extra_turns_after_all_connections_have_no_current_connection(self) -> None:
        messages = [
            HumanMessage("Linuxのしくみ"),
            AIMessage("問い1"),
            HumanMessage("答え1"),
            AIMessage("問い2"),
            HumanMessage("答え2"),
            AIMessage("おわり"),
            HumanMessage("ありがとう"),
        ]
        with patch("graph.nodes.synthesis.llm") as mock_llm:
            mock_llm.ainvoke = AsyncMock(return_value=AIMessage("どういたしまして"))
            from graph.nodes.synthesis import synthesis_dialogue

            await synthesis_dialogue(_state(messages))

        assert "## 直前に聞いたつながり\nなし" in _system_prompt(mock_llm)


def _pool() -> MagicMock:
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool


class TestFinishSynthesis:
    async def _run(self, output: SynthesisInsightsOutput) -> AsyncMock:
        messages = [HumanMessage("Linuxのしくみ"), AIMessage("問い1"), HumanMessage("答え1")]
        with (
            patch("graph.nodes.synthesis.llm_structured") as mock_llm,
            patch("graph.nodes.synthesis.get_pool", AsyncMock(return_value=_pool())),
            patch("graph.nodes.synthesis.synthesis_insight_repository.insert_many", AsyncMock()) as mock_insert,
        ):
            mock_llm.with_structured_output = MagicMock(return_value=MagicMock(ainvoke=AsyncMock(return_value=output)))
            from graph.nodes.synthesis import finish_synthesis

            await finish_synthesis(_state(messages, should_generate_note=True))
        return mock_insert

    async def test_saves_insights_by_connection_title(self) -> None:
        mock_insert = await self._run(
            SynthesisInsightsOutput(
                insights=[
                    SynthesisInsightDraft(connection_id="c1", content=" 説明 "),
                    SynthesisInsightDraft(connection_id="c9", content="知らないつながり"),
                ]
            )
        )

        assert mock_insert.call_args.kwargs["insights"] == [("コンテキストスイッチ", "説明")]
        assert mock_insert.call_args.kwargs["collection_id"] == COLLECTION_ID

    async def test_nothing_explained_writes_nothing(self) -> None:
        mock_insert = await self._run(SynthesisInsightsOutput(insights=[]))

        mock_insert.assert_not_called()
