from collections.abc import Iterator
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.routes.note_revision import list_note_revisions

_USER_ID = "user-123"


@pytest.fixture(autouse=True)
def _note_exists() -> Iterator[None]:
    with patch("api.routes.note_revision.note_repository.find_by_id", new=AsyncMock(return_value={"id": uuid4()})):
        yield


def _make_revision_record() -> dict[str, object]:
    return {
        "id": uuid4(),
        "note_id": uuid4(),
        "content": "- 復習で深まった点",
        "created_at": datetime(2026, 6, 1),
    }


class TestListNoteRevisions:
    async def test_returns_revisions(self) -> None:
        records = [_make_revision_record(), _make_revision_record()]
        mock_db = MagicMock()

        with patch(
            "api.routes.note_revision.note_revision_repository.find_by_note_id",
            new=AsyncMock(return_value=records),
        ):
            result = await list_note_revisions(note_id=uuid4(), current_user_id=_USER_ID, db=mock_db)

        assert len(result.revisions) == 2

    async def test_returns_empty_list(self) -> None:
        mock_db = MagicMock()

        with patch(
            "api.routes.note_revision.note_revision_repository.find_by_note_id",
            new=AsyncMock(return_value=[]),
        ):
            result = await list_note_revisions(note_id=uuid4(), current_user_id=_USER_ID, db=mock_db)

        assert result.revisions == []

    async def test_missing_or_other_users_note_is_404(self) -> None:
        find_revisions = AsyncMock(return_value=[])
        with (
            patch("api.routes.note_revision.note_repository.find_by_id", new=AsyncMock(return_value=None)),
            patch("api.routes.note_revision.note_revision_repository.find_by_note_id", new=find_revisions),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await list_note_revisions(note_id=uuid4(), current_user_id=_USER_ID, db=MagicMock())

        assert exc_info.value.status_code == 404
        find_revisions.assert_not_awaited()
