from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from langchain_core.messages import HumanMessage

from graph.output_schemas import DialogueAnalysis, FeedbackOutput, NoteContent, ReviewAddendum
from graph.state import LearningState

NOTE_ID = UUID("00000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
USER_ID = "user-abc"

FAKE_NOTE_UNEDITED = {
    "id": NOTE_ID,
    "user_id": USER_ID,
    "topic": "二分探索",
    "content": "二分探索は探索範囲を半分に絞る手法です。",
    "summary": "二分探索の要約",
    "manually_edited_at": None,
}

FAKE_NOTE_EDITED = {
    **FAKE_NOTE_UNEDITED,
    "content": "ユーザーが手で仕上げた本文。",
    "manually_edited_at": datetime(2026, 6, 1, tzinfo=UTC),
}

FAKE_REVISED_NOTE = NoteContent(topic="二分探索", content="改訂後の本文", summary="改訂後の要約")
FAKE_ADDENDUM = ReviewAddendum(content="- 計算量が O(log n) である点を新たに理解した")

FAKE_ANALYSIS = DialogueAnalysis(
    accurate_understanding=["二分探索の手順を説明できた"],
    misconceptions=[],
    ambiguous_expressions=[],
    unmentioned_concepts=[],
    depth_level="principle",
)
FAKE_FEEDBACK_OUTPUT = FeedbackOutput(
    understanding_level="high",
    strength=["手順を理解している"],
    improvement_points=["計算量にも触れると良い"],
)


def _make_structured_mock() -> MagicMock:
    def _route(schema: type) -> AsyncMock:
        if schema is NoteContent:
            return AsyncMock(ainvoke=AsyncMock(return_value=FAKE_REVISED_NOTE))
        if schema is ReviewAddendum:
            return AsyncMock(ainvoke=AsyncMock(return_value=FAKE_ADDENDUM))
        if schema is DialogueAnalysis:
            return AsyncMock(ainvoke=AsyncMock(return_value=FAKE_ANALYSIS))
        return AsyncMock(ainvoke=AsyncMock(return_value=FAKE_FEEDBACK_OUTPUT))

    return MagicMock(side_effect=_route)


def _make_state(**overrides: object) -> LearningState:
    base: dict[str, object] = {
        "user_id": USER_ID,
        "dialogue_session_id": SESSION_ID,
        "note_id": NOTE_ID,
        "messages": [HumanMessage(content="二分探索は半分に絞る手法です")],
        "topic": "二分探索",
        "turn_count": 3,
        "should_generate_note": True,
        "session_type": "review",
    }
    base.update(overrides)
    return cast(LearningState, base)


@pytest.fixture()
def mock_pool() -> tuple[MagicMock, AsyncMock]:
    conn = AsyncMock()
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool, conn


class TestUpdateNoteAndFeedback:
    async def test_unedited_note_is_fully_regenerated(self, mock_pool: tuple[MagicMock, AsyncMock]) -> None:
        pool, _conn = mock_pool

        with (
            patch("graph.nodes.update_note_and_feedback.get_pool", AsyncMock(return_value=pool)),
            patch("graph.nodes.update_note_and_feedback.llm_structured") as mock_llm,
            patch(
                "graph.nodes.update_note_and_feedback.note_repository.find_by_id",
                AsyncMock(return_value=dict(FAKE_NOTE_UNEDITED)),
            ),
            patch("graph.nodes.update_note_and_feedback.note_repository.update", AsyncMock()) as mock_update,
            patch(
                "graph.nodes.update_note_and_feedback.note_revision_repository.insert", AsyncMock()
            ) as mock_revision_insert,
            patch("graph.nodes.update_note_and_feedback.feedback_repository.insert", AsyncMock()),
            patch(
                "graph.nodes.update_note_and_feedback.review_schedule_repository.find_by_note_id",
                AsyncMock(return_value=None),
            ),
            patch("graph.nodes.update_note_and_feedback.review_schedule_repository.insert", AsyncMock()),
        ):
            mock_llm.with_structured_output = _make_structured_mock()

            from graph.nodes.update_note_and_feedback import update_note_and_feedback

            result = await update_note_and_feedback(_make_state())

        assert result == {}
        mock_update.assert_called_once()
        mock_revision_insert.assert_not_called()

    async def test_manually_edited_note_appends_revision_without_overwriting(
        self, mock_pool: tuple[MagicMock, AsyncMock]
    ) -> None:
        pool, _conn = mock_pool

        with (
            patch("graph.nodes.update_note_and_feedback.get_pool", AsyncMock(return_value=pool)),
            patch("graph.nodes.update_note_and_feedback.llm_structured") as mock_llm,
            patch(
                "graph.nodes.update_note_and_feedback.note_repository.find_by_id",
                AsyncMock(return_value=dict(FAKE_NOTE_EDITED)),
            ),
            patch("graph.nodes.update_note_and_feedback.note_repository.update", AsyncMock()) as mock_update,
            patch(
                "graph.nodes.update_note_and_feedback.note_revision_repository.insert", AsyncMock()
            ) as mock_revision_insert,
            patch("graph.nodes.update_note_and_feedback.feedback_repository.insert", AsyncMock()),
            patch(
                "graph.nodes.update_note_and_feedback.review_schedule_repository.find_by_note_id",
                AsyncMock(return_value=None),
            ),
            patch("graph.nodes.update_note_and_feedback.review_schedule_repository.insert", AsyncMock()),
        ):
            mock_llm.with_structured_output = _make_structured_mock()

            from graph.nodes.update_note_and_feedback import update_note_and_feedback

            result = await update_note_and_feedback(_make_state())

        assert result == {}
        mock_update.assert_not_called()
        mock_revision_insert.assert_called_once()
        kwargs = mock_revision_insert.call_args.kwargs
        assert kwargs["note_id"] == NOTE_ID
        assert kwargs["dialogue_session_id"] == SESSION_ID
        assert kwargs["content"] == FAKE_ADDENDUM.content

    async def test_feedback_and_schedule_updated_for_edited_note(self, mock_pool: tuple[MagicMock, AsyncMock]) -> None:
        pool, _conn = mock_pool

        with (
            patch("graph.nodes.update_note_and_feedback.get_pool", AsyncMock(return_value=pool)),
            patch("graph.nodes.update_note_and_feedback.llm_structured") as mock_llm,
            patch(
                "graph.nodes.update_note_and_feedback.note_repository.find_by_id",
                AsyncMock(return_value=dict(FAKE_NOTE_EDITED)),
            ),
            patch("graph.nodes.update_note_and_feedback.note_revision_repository.insert", AsyncMock()),
            patch("graph.nodes.update_note_and_feedback.feedback_repository.insert", AsyncMock()) as mock_feedback,
            patch(
                "graph.nodes.update_note_and_feedback.review_schedule_repository.find_by_note_id",
                AsyncMock(return_value=None),
            ),
            patch(
                "graph.nodes.update_note_and_feedback.review_schedule_repository.insert", AsyncMock()
            ) as mock_schedule_insert,
        ):
            mock_llm.with_structured_output = _make_structured_mock()

            from graph.nodes.update_note_and_feedback import update_note_and_feedback

            await update_note_and_feedback(_make_state())

        mock_feedback.assert_called_once()
        mock_schedule_insert.assert_called_once()
