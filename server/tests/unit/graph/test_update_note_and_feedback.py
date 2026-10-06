import json
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from langchain_core.messages import HumanMessage

from graph.output_schemas import DialogueAnalysis, FeedbackOutput, ImprovementPoint, NoteContent, ReviewAddendum
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
    "aspect_map": json.dumps(
        {"root": "二分探索", "aspects": [{"name": "計算量", "summary": "", "coverage": "partial", "children": []}]}
    ),
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
    improvement_points=[ImprovementPoint(text="計算量にも触れると良い", aspect_id="a1")],
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


class TestFeedbackAspectLinks:
    async def _run(
        self, note: dict[str, object], mock_pool: tuple[MagicMock, AsyncMock]
    ) -> tuple[AsyncMock, AsyncMock]:
        pool, _conn = mock_pool
        feedback_llm = AsyncMock(ainvoke=AsyncMock(return_value=FAKE_FEEDBACK_OUTPUT))

        def _route(schema: type) -> AsyncMock:
            if schema is FeedbackOutput:
                return feedback_llm
            return _make_structured_mock()(schema)  # type: ignore[no-any-return]

        with (
            patch("graph.nodes.update_note_and_feedback.get_pool", AsyncMock(return_value=pool)),
            patch("graph.nodes.update_note_and_feedback.llm_structured") as mock_llm,
            patch("graph.nodes.update_note_and_feedback.note_repository.find_by_id", AsyncMock(return_value=note)),
            patch("graph.nodes.update_note_and_feedback.note_repository.update", AsyncMock()),
            patch("graph.nodes.update_note_and_feedback.feedback_repository.insert", AsyncMock()) as insert,
            patch(
                "graph.nodes.update_note_and_feedback.review_schedule_repository.find_by_note_id",
                AsyncMock(return_value=None),
            ),
            patch("graph.nodes.update_note_and_feedback.review_schedule_repository.insert", AsyncMock()),
        ):
            mock_llm.with_structured_output = MagicMock(side_effect=_route)

            from graph.nodes.update_note_and_feedback import update_note_and_feedback

            await update_note_and_feedback(_make_state())
        return insert, feedback_llm.ainvoke

    async def test_links_improvements_to_existing_aspect_map(self, mock_pool: tuple[MagicMock, AsyncMock]) -> None:
        insert, _ = await self._run(dict(FAKE_NOTE_UNEDITED), mock_pool)

        items = json.loads(insert.call_args.kwargs["improvement_items"])
        assert items == [{"text": "計算量にも触れると良い", "aspect_id": "a1"}]

    async def test_feedback_prompt_lists_the_note_aspects(self, mock_pool: tuple[MagicMock, AsyncMock]) -> None:
        _, feedback_ainvoke = await self._run(dict(FAKE_NOTE_UNEDITED), mock_pool)

        system_message = feedback_ainvoke.call_args.args[0][0]
        assert "- a1: 計算量" in system_message.content

    async def test_note_without_aspect_map_links_nothing(self, mock_pool: tuple[MagicMock, AsyncMock]) -> None:
        insert, feedback_ainvoke = await self._run({**FAKE_NOTE_UNEDITED, "aspect_map": None}, mock_pool)

        items = json.loads(insert.call_args.kwargs["improvement_items"])
        assert items == [{"text": "計算量にも触れると良い", "aspect_id": None}]
        assert "空文字" in feedback_ainvoke.call_args.args[0][0].content


class TestAdvanceReviewSchedule:
    NOW = datetime(2026, 3, 26, 3, 0, tzinfo=UTC)

    async def _advance(self, schedule: dict[str, object] | None) -> tuple[AsyncMock, AsyncMock]:
        from freezegun import freeze_time

        from graph.nodes.update_note_and_feedback import _advance_review_schedule

        with (
            freeze_time(self.NOW),
            patch(
                "graph.nodes.update_note_and_feedback.review_schedule_repository.find_by_note_id",
                AsyncMock(return_value=schedule),
            ),
            patch("graph.nodes.update_note_and_feedback.review_schedule_repository.insert", AsyncMock()) as insert,
            patch(
                "graph.nodes.update_note_and_feedback.review_schedule_repository.update_schedule", AsyncMock()
            ) as update,
        ):
            await _advance_review_schedule(conn=AsyncMock(), note_id=NOTE_ID)
        return insert, update

    async def test_due_review_counts_and_uses_the_next_interval(self) -> None:
        _insert, update = await self._advance({"review_count": 0, "next_review_at": self.NOW - timedelta(hours=1)})

        update.assert_called_once()
        assert update.call_args.kwargs["review_count"] == 1
        assert update.call_args.kwargs["next_review_at"] == self.NOW + timedelta(days=3)

    async def test_review_due_later_today_counts(self) -> None:
        _insert, update = await self._advance({"review_count": 2, "next_review_at": self.NOW + timedelta(hours=5)})

        update.assert_called_once()
        assert update.call_args.kwargs["review_count"] == 3

    async def test_early_review_leaves_the_schedule_untouched(self) -> None:
        insert, update = await self._advance({"review_count": 1, "next_review_at": self.NOW + timedelta(days=2)})

        update.assert_not_called()
        insert.assert_not_called()

    async def test_missing_schedule_is_created(self) -> None:
        insert, update = await self._advance(None)

        insert.assert_called_once()
        assert insert.call_args.kwargs["next_review_at"] == self.NOW + timedelta(days=1)
        update.assert_not_called()
