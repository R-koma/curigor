from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from api.routes.study_memo import get_study_memo, list_study_memos

_USER_ID = "user-123"


def _memo() -> dict[str, object]:
    return {
        "id": uuid4(),
        "dialogue_session_id": uuid4(),
        "topic": "二分探索",
        "source": "",
        "summary": "",
        "overview": [{"aspect_id": "a", "name": "比較", "summary": "s", "is_core": True}],
        "glossary": [{"term": "計算量", "reading": "けいさんりょう", "meaning": "手間"}],
        "questions": [{"question": "なぜ並べるのか", "answer": "半分を捨てるため"}],
        "depth_map": {"topic": "二分探索", "aspects": []},
        "created_at": datetime(2026, 10, 13),
    }


async def test_get_returns_the_memo_without_the_depth_map() -> None:
    memo = _memo()
    memo_id = memo["id"]
    assert isinstance(memo_id, UUID)
    with patch("api.routes.study_memo.study_memo_repository.find_by_id", new=AsyncMock(return_value=memo)):
        result = await get_study_memo(memo_id, current_user_id=_USER_ID, db=MagicMock())

    dumped = result.model_dump()
    assert dumped["glossary"][0]["reading"] == "けいさんりょう"
    assert dumped["questions"][0]["answer"] == "半分を捨てるため"
    assert "depth_map" not in dumped
    assert "dialogue_session_id" not in dumped


async def test_get_returns_404_for_a_missing_memo() -> None:
    with (
        patch("api.routes.study_memo.study_memo_repository.find_by_id", new=AsyncMock(return_value=None)),
        pytest.raises(HTTPException) as exc,
    ):
        await get_study_memo(uuid4(), current_user_id=_USER_ID, db=MagicMock())

    assert exc.value.status_code == 404


async def test_list_returns_summaries() -> None:
    rows = [
        {
            "id": uuid4(),
            "topic": "二分探索",
            "source": "",
            "created_at": datetime(2026, 10, 13),
            "handed_over": False,
            "overview": [
                {"aspect_id": "a", "name": "比較", "summary": "s", "is_core": True},
                {"aspect_id": "b", "name": "計算量", "summary": "s", "is_core": False},
            ],
            "glossary_count": 3,
            "question_count": 2,
        }
    ]
    with patch("api.routes.study_memo.study_memo_repository.find_by_user_id", new=AsyncMock(return_value=rows)):
        result = await list_study_memos(current_user_id=_USER_ID, db=MagicMock())

    assert [m.topic for m in result.memos] == ["二分探索"]
    dumped = result.memos[0].model_dump()
    assert dumped["handed_over"] is False
    assert dumped["aspects"] == [{"name": "比較", "is_core": True}, {"name": "計算量", "is_core": False}]
    assert dumped["glossary_count"] == 3
    assert dumped["question_count"] == 2
    assert "overview" not in dumped


async def test_aspects_without_indices_are_returned_with_empty_lists() -> None:
    memo = _memo()
    memo["overview"] = [{"aspect_id": "a1", "name": "比較", "summary": "", "is_core": True}]
    memo["summary"] = ""
    memo_id = memo["id"]
    assert isinstance(memo_id, UUID)
    with patch("api.routes.study_memo.study_memo_repository.find_by_id", new=AsyncMock(return_value=memo)):
        result = await get_study_memo(memo_id, current_user_id=_USER_ID, db=MagicMock())

    dumped = result.model_dump()
    assert dumped["overview"][0]["question_indices"] == []
    assert dumped["overview"][0]["term_indices"] == []
    assert dumped["summary"] == ""
