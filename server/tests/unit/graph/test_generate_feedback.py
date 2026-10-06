from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from langchain_core.messages import HumanMessage

from graph.output_schemas import DialogueAnalysis, FeedbackOutput
from graph.state import LearningState

NOTE_ID = UUID("00000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
USER_ID = "user-abc"

FAKE_NOTE = {
    "id": NOTE_ID,
    "user_id": USER_ID,
    "topic": "Pythonの基礎",
    "content": "Pythonは動的型付け言語です。",
    "summary": "Pythonの基礎まとめ",
}

FAKE_FEEDBACK_OUTPUT = FeedbackOutput(
    understanding_level="high",
    strength=["概念をよく理解している"],
    improvement_points=["具体例をもっと使うと良い"],
)

FAKE_ANALYSIS = DialogueAnalysis(
    accurate_understanding=["Pythonが動的型付けであることを理解している"],
    misconceptions=[],
    ambiguous_expressions=[],
    unmentioned_concepts=[],
    depth_level="principle",
)


def _make_structured_mock(feedback_output: object) -> MagicMock:
    """with_structured_output(DialogueAnalysis | FeedbackOutput) の両方に対応するモックを返す"""

    def _route(schema: type) -> AsyncMock:
        if schema is DialogueAnalysis:
            return AsyncMock(ainvoke=AsyncMock(return_value=FAKE_ANALYSIS))
        return AsyncMock(ainvoke=AsyncMock(return_value=feedback_output))

    return MagicMock(side_effect=_route)


def _make_state(**overrides: object) -> LearningState:
    base: dict[str, object] = {
        "user_id": USER_ID,
        "dialogue_session_id": SESSION_ID,
        "note_id": NOTE_ID,
        "messages": [HumanMessage(content="Pythonとは何ですか？")],
        "topic": "Pythonの基礎",
        "turn_count": 3,
        "should_generate_note": True,
        "session_type": "review",
        "note_content": "",
        "note_summary": "",
    }
    base.update(overrides)
    return cast(LearningState, base)


@pytest.fixture()
def mock_pool() -> tuple[MagicMock, AsyncMock]:
    """get_pool が返す asyncpg プールのモック"""
    conn = AsyncMock()
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool, conn


class TestGenerateFeedback:
    async def test_insert_schedule_when_no_existing(self, mock_pool: tuple[MagicMock, AsyncMock]) -> None:
        """既存スケジュールがない場合、review_schedule_repository.insert が呼ばれる"""
        pool, conn = mock_pool

        with (
            patch("graph.nodes.generate_feedback.get_pool", AsyncMock(return_value=pool)),
            patch("graph.nodes.generate_feedback.llm_structured") as mock_llm,
            patch("graph.nodes.generate_feedback.note_repository.find_by_id", AsyncMock(return_value=FAKE_NOTE)),
            patch("graph.nodes.generate_feedback.feedback_repository.insert", AsyncMock()),
            patch(
                "graph.nodes.generate_feedback.review_schedule_repository.find_by_note_id",
                AsyncMock(return_value=None),
            ),
            patch("graph.nodes.generate_feedback.review_schedule_repository.insert", AsyncMock()) as mock_rs_insert,
            patch(
                "graph.nodes.generate_feedback.review_schedule_repository.update_schedule", AsyncMock()
            ) as mock_rs_update,
        ):
            mock_llm.with_structured_output = _make_structured_mock(FAKE_FEEDBACK_OUTPUT)

            from graph.nodes.generate_feedback import generate_feedback

            result = await generate_feedback(_make_state())

        assert result == {}
        mock_rs_insert.assert_called_once()
        mock_rs_update.assert_not_called()

    async def test_existing_schedule_is_left_untouched(self, mock_pool: tuple[MagicMock, AsyncMock]) -> None:
        """学習は復習の回数に数えないので、既存スケジュールを進めない"""
        pool, conn = mock_pool
        existing = {"review_count": 2, "next_review_at": None}

        with (
            patch("graph.nodes.generate_feedback.get_pool", AsyncMock(return_value=pool)),
            patch("graph.nodes.generate_feedback.llm_structured") as mock_llm,
            patch("graph.nodes.generate_feedback.note_repository.find_by_id", AsyncMock(return_value=FAKE_NOTE)),
            patch("graph.nodes.generate_feedback.feedback_repository.insert", AsyncMock()),
            patch(
                "graph.nodes.generate_feedback.review_schedule_repository.find_by_note_id",
                AsyncMock(return_value=existing),
            ),
            patch("graph.nodes.generate_feedback.review_schedule_repository.insert", AsyncMock()) as mock_rs_insert,
            patch(
                "graph.nodes.generate_feedback.review_schedule_repository.update_schedule", AsyncMock()
            ) as mock_rs_update,
        ):
            mock_llm.with_structured_output = _make_structured_mock(FAKE_FEEDBACK_OUTPUT)

            from graph.nodes.generate_feedback import generate_feedback

            result = await generate_feedback(_make_state())

        assert result == {}
        mock_rs_update.assert_not_called()
        mock_rs_insert.assert_not_called()

    async def test_raises_when_note_not_found(self, mock_pool: tuple[MagicMock, AsyncMock]) -> None:
        """`note_repository.find_by_id` が None を返したとき RuntimeError が発生する"""
        pool, conn = mock_pool

        with (
            patch("graph.nodes.generate_feedback.get_pool", AsyncMock(return_value=pool)),
            patch("graph.nodes.generate_feedback.llm_structured") as mock_llm,
            patch("graph.nodes.generate_feedback.note_repository.find_by_id", AsyncMock(return_value=None)),
        ):
            mock_llm.with_structured_output = _make_structured_mock(FAKE_FEEDBACK_OUTPUT)

            from graph.nodes.generate_feedback import generate_feedback

            with pytest.raises(RuntimeError, match=f"Note {NOTE_ID} not found"):
                await generate_feedback(_make_state())

    async def test_raises_when_llm_returns_wrong_type(self, mock_pool: tuple[MagicMock, AsyncMock]) -> None:
        """LLM が FeedbackOutput 以外を返したとき RuntimeError が発生する"""
        pool, conn = mock_pool

        with (
            patch("graph.nodes.generate_feedback.get_pool", AsyncMock(return_value=pool)),
            patch("graph.nodes.generate_feedback.llm_structured") as mock_llm,
            patch("graph.nodes.generate_feedback.note_repository.find_by_id", AsyncMock(return_value=FAKE_NOTE)),
            patch("graph.nodes.generate_feedback.feedback_repository.insert", AsyncMock()),
        ):
            mock_llm.with_structured_output = _make_structured_mock({"wrong": "type"})

            from graph.nodes.generate_feedback import generate_feedback

            with pytest.raises(RuntimeError, match="LLM did not return structured FeedbackOutput"):
                await generate_feedback(_make_state())

    async def test_feedback_insert_called_with_correct_args(self, mock_pool: tuple[MagicMock, AsyncMock]) -> None:
        """`feedback_repository.insert` が正しい引数で呼ばれる"""
        pool, conn = mock_pool

        with (
            patch("graph.nodes.generate_feedback.get_pool", AsyncMock(return_value=pool)),
            patch("graph.nodes.generate_feedback.llm_structured") as mock_llm,
            patch("graph.nodes.generate_feedback.note_repository.find_by_id", AsyncMock(return_value=FAKE_NOTE)),
            patch("graph.nodes.generate_feedback.feedback_repository.insert", AsyncMock()) as mock_fb_insert,
            patch(
                "graph.nodes.generate_feedback.review_schedule_repository.find_by_note_id",
                AsyncMock(return_value=None),
            ),
            patch("graph.nodes.generate_feedback.review_schedule_repository.insert", AsyncMock()),
        ):
            mock_llm.with_structured_output = _make_structured_mock(FAKE_FEEDBACK_OUTPUT)

            from graph.nodes.generate_feedback import generate_feedback

            await generate_feedback(_make_state())

        mock_fb_insert.assert_called_once()
        _, kwargs = mock_fb_insert.call_args
        assert kwargs["note_id"] == NOTE_ID
        assert kwargs["dialogue_session_id"] == SESSION_ID
        assert kwargs["understanding_level"] == "high"
        assert kwargs["strength"] == "概念をよく理解している"
        assert kwargs["improvements"] == "具体例をもっと使うと良い"
