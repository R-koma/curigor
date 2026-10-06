from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from api.routes.feedback import list_feedbacks

_USER_ID = "user-123"


def _make_feedback_record() -> dict[str, object]:
    return {
        "id": uuid4(),
        "note_id": uuid4(),
        "dialogue_session_id": uuid4(),
        "understanding_level": "high",
        "strength": "基本概念を正確に説明できた",
        "improvements": "応用例をもっと挙げられるとよい",
        "session_type": "review",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }


class TestListFeedbacks:
    async def test_returns_feedback_list(self) -> None:
        note_id = uuid4()
        records = [_make_feedback_record(), _make_feedback_record()]
        mock_db = MagicMock()

        with patch(
            "api.routes.feedback.feedback_repository.find_by_note_id",
            new=AsyncMock(return_value=records),
        ):
            result = await list_feedbacks(note_id=note_id, current_user_id=_USER_ID, db=mock_db)

        assert len(result.feedbacks) == 2

    async def test_returns_empty_list_when_no_feedbacks(self) -> None:
        note_id = uuid4()
        mock_db = MagicMock()

        with patch(
            "api.routes.feedback.feedback_repository.find_by_note_id",
            new=AsyncMock(return_value=[]),
        ):
            result = await list_feedbacks(note_id=note_id, current_user_id=_USER_ID, db=mock_db)

        assert result.feedbacks == []

    async def test_returns_session_type_and_allows_missing_session(self) -> None:
        record = {**_make_feedback_record(), "dialogue_session_id": None, "session_type": None}
        mock_db = MagicMock()

        with patch(
            "api.routes.feedback.feedback_repository.find_by_note_id",
            new=AsyncMock(return_value=[record]),
        ):
            result = await list_feedbacks(note_id=uuid4(), current_user_id=_USER_ID, db=mock_db)

        assert result.feedbacks[0].dialogue_session_id is None
        assert result.feedbacks[0].session_type is None


class TestImprovementItems:
    async def test_parses_stored_json_and_keeps_legacy_rows_none(self) -> None:
        linked = {
            **_make_feedback_record(),
            "improvement_items": '[{"text": "t", "aspect_id": "a1"}, {"text": "u", "aspect_id": null}]',
        }
        legacy = {**_make_feedback_record(), "improvement_items": None}

        with patch(
            "api.routes.feedback.feedback_repository.find_by_note_id",
            new=AsyncMock(return_value=[linked, legacy]),
        ):
            result = await list_feedbacks(note_id=uuid4(), current_user_id=_USER_ID, db=MagicMock())

        assert [i.model_dump() for i in result.feedbacks[0].improvement_items or []] == [
            {"text": "t", "aspect_id": "a1"},
            {"text": "u", "aspect_id": None},
        ]
        assert result.feedbacks[1].improvement_items is None
