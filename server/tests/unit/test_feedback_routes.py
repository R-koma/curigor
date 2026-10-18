import json
from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.routes.feedback import list_feedbacks
from schemas.feedback import FeedbackResponse

_USER_ID = "user-123"


@pytest.fixture(autouse=True)
def _note_exists() -> Iterator[None]:
    with patch("api.routes.feedback.note_repository.find_by_id", new=AsyncMock(return_value={"id": uuid4()})):
        yield


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


def test_feedback_response_parses_review_results_string() -> None:
    record = {
        **_make_feedback_record(),
        "review_results": json.dumps(
            [{"point_id": "p1", "point": "観点", "question": "質問", "status": "explained", "aspect_id": None}],
            ensure_ascii=False,
        ),
    }

    parsed = FeedbackResponse(**record)  # type: ignore[arg-type]

    assert parsed.review_results is not None
    assert parsed.review_results[0].status == "explained"


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

    async def test_missing_or_other_users_note_is_404(self) -> None:
        find_feedbacks = AsyncMock(return_value=[])
        with (
            patch("api.routes.feedback.note_repository.find_by_id", new=AsyncMock(return_value=None)),
            patch("api.routes.feedback.feedback_repository.find_by_note_id", new=find_feedbacks),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await list_feedbacks(note_id=uuid4(), current_user_id=_USER_ID, db=MagicMock())

        assert exc_info.value.status_code == 404
        find_feedbacks.assert_not_awaited()


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
