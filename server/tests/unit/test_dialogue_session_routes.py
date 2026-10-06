import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.responses import Response

from api.routes.dialogue_session import get_active_session, get_session_image, get_session_messages
from schemas.dialogue_session import ActiveSessionResponse, SessionMessagesResponse

_USER_ID = "user-123"


def _make_session(
    session_id: UUID | None = None,
    status: str = "in_progress",
    session_type: str = "learning",
    note_id: UUID | None = None,
) -> dict[str, object]:
    return {
        "id": session_id or uuid4(),
        "user_id": _USER_ID,
        "session_type": session_type,
        "status": status,
        "note_id": note_id,
        "started_at": datetime(2026, 1, 1, 0, 0, 0),
        "ended_at": None,
        "topic": "React Hooks",
    }


def _make_message(
    role: str = "user",
    content: str = "hello",
    order: int = 1,
    intake_card: str | None = None,
    intake_answers: str | None = None,
    topic_correction_card: str | None = None,
    topic_correction_answer: str | None = None,
) -> dict[str, object]:
    return {
        "id": uuid4(),
        "role": role,
        "content": content,
        "message_order": order,
        "intake_card": intake_card,
        "intake_answers": intake_answers,
        "topic_correction_card": topic_correction_card,
        "topic_correction_answer": topic_correction_answer,
    }


class TestGetActiveSession:
    async def test_returns_204_when_no_active_session(self) -> None:
        mock_db = MagicMock()

        with patch(
            "api.routes.dialogue_session.dialogue_session_repository.find_resumable_by_user",
            new=AsyncMock(return_value=None),
        ):
            result = await get_active_session(current_user_id=_USER_ID, db=mock_db)

        assert isinstance(result, Response)
        assert result.status_code == 204

    async def test_returns_active_session(self) -> None:
        session_id = uuid4()
        session = _make_session(session_id=session_id)
        mock_db = MagicMock()

        with patch(
            "api.routes.dialogue_session.dialogue_session_repository.find_resumable_by_user",
            new=AsyncMock(return_value=session),
        ):
            result = await get_active_session(current_user_id=_USER_ID, db=mock_db)

        assert isinstance(result, ActiveSessionResponse)
        assert result.session_id == session_id
        assert result.session_type == "learning"

    async def test_returns_disconnect_session(self) -> None:
        session = _make_session(status="disconnect", session_type="review")
        mock_db = MagicMock()

        with patch(
            "api.routes.dialogue_session.dialogue_session_repository.find_resumable_by_user",
            new=AsyncMock(return_value=session),
        ):
            result = await get_active_session(current_user_id=_USER_ID, db=mock_db)

        assert isinstance(result, ActiveSessionResponse)
        assert result.status == "disconnect"

    async def test_returns_note_id_for_review_session(self) -> None:
        note_id = uuid4()
        session = _make_session(session_type="review", note_id=note_id)
        mock_db = MagicMock()

        with patch(
            "api.routes.dialogue_session.dialogue_session_repository.find_resumable_by_user",
            new=AsyncMock(return_value=session),
        ):
            result = await get_active_session(current_user_id=_USER_ID, db=mock_db)

        assert isinstance(result, ActiveSessionResponse)
        assert result.note_id == note_id


class TestGetSessionMessages:
    async def test_raises_404_when_session_not_found(self) -> None:
        mock_db = MagicMock()

        with (
            patch(
                "api.routes.dialogue_session.dialogue_session_repository.find_by_id",
                new=AsyncMock(return_value=None),
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_session_messages(session_id=uuid4(), current_user_id=_USER_ID, db=mock_db)

        assert exc_info.value.status_code == 404

    async def test_returns_session_with_messages(self) -> None:
        session_id = uuid4()
        session = _make_session(session_id=session_id)
        messages = [
            _make_message("user", "Pythonを教えて", 1),
            _make_message("assistant", "Pythonはプログラミング言語です", 2),
        ]
        mock_db = MagicMock()

        with (
            patch(
                "api.routes.dialogue_session.dialogue_session_repository.find_by_id",
                new=AsyncMock(return_value=session),
            ),
            patch(
                "api.routes.dialogue_session.dialogue_message_repository.find_by_session_id",
                new=AsyncMock(return_value=messages),
            ),
            patch(
                "api.routes.dialogue_session.dialogue_message_image_repository.find_by_session_id",
                new=AsyncMock(return_value=[]),
            ),
        ):
            result = await get_session_messages(session_id=session_id, current_user_id=_USER_ID, db=mock_db)

        assert isinstance(result, SessionMessagesResponse)
        assert result.session_id == session_id
        assert len(result.messages) == 2
        assert result.messages[0].role == "user"
        assert result.messages[1].role == "assistant"

    async def test_returns_session_with_no_messages(self) -> None:
        session_id = uuid4()
        session = _make_session(session_id=session_id)
        mock_db = MagicMock()

        with (
            patch(
                "api.routes.dialogue_session.dialogue_session_repository.find_by_id",
                new=AsyncMock(return_value=session),
            ),
            patch(
                "api.routes.dialogue_session.dialogue_message_repository.find_by_session_id",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "api.routes.dialogue_session.dialogue_message_image_repository.find_by_session_id",
                new=AsyncMock(return_value=[]),
            ),
        ):
            result = await get_session_messages(session_id=session_id, current_user_id=_USER_ID, db=mock_db)

        assert result.messages == []

    async def test_returns_note_id_when_present(self) -> None:
        session_id = uuid4()
        note_id = uuid4()
        session = _make_session(session_id=session_id, status="completed", note_id=note_id)
        mock_db = MagicMock()

        with (
            patch(
                "api.routes.dialogue_session.dialogue_session_repository.find_by_id",
                new=AsyncMock(return_value=session),
            ),
            patch(
                "api.routes.dialogue_session.dialogue_message_repository.find_by_session_id",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "api.routes.dialogue_session.dialogue_message_image_repository.find_by_session_id",
                new=AsyncMock(return_value=[]),
            ),
        ):
            result = await get_session_messages(session_id=session_id, current_user_id=_USER_ID, db=mock_db)

        assert result.note_id == note_id


class TestGetSessionMessagesIntake:
    async def test_returns_topic_and_intake_card(self) -> None:
        session_id = uuid4()
        session = _make_session(session_id=session_id)
        card = json.dumps(
            {"questions": [{"key": "source", "header": "教材", "question": "q", "options": [{"label": "書籍"}]}]}
        )
        messages = [
            _make_message("user", "Reactのフック", 1),
            _make_message("assistant", "lead", 2, intake_card=card),
        ]
        with (
            patch(
                "api.routes.dialogue_session.dialogue_session_repository.find_by_id",
                new=AsyncMock(return_value=session),
            ),
            patch(
                "api.routes.dialogue_session.dialogue_message_repository.find_by_session_id",
                new=AsyncMock(return_value=messages),
            ),
            patch(
                "api.routes.dialogue_session.dialogue_message_image_repository.find_by_session_id",
                new=AsyncMock(return_value=[]),
            ),
        ):
            result = await get_session_messages(session_id=session_id, current_user_id=_USER_ID, db=MagicMock())

        assert result.topic == "React Hooks"
        assert result.messages[0].intake_card is None
        assert result.messages[1].intake_card is not None
        assert result.messages[1].intake_card.questions[0].options[0].label == "書籍"

    async def test_returns_intake_answers_only_for_card_replies(self) -> None:
        session_id = uuid4()
        session = _make_session(session_id=session_id)
        answers = json.dumps({"purpose": "基礎知識を身につける", "source": ["入門書"], "prior_knowledge": ""})
        messages = [
            _make_message("user", "目的: 基礎知識を身につける\n教材: 入門書", 3, intake_answers=answers),
            _make_message("user", "自由文の返信", 5),
        ]
        with (
            patch(
                "api.routes.dialogue_session.dialogue_session_repository.find_by_id",
                new=AsyncMock(return_value=session),
            ),
            patch(
                "api.routes.dialogue_session.dialogue_message_repository.find_by_session_id",
                new=AsyncMock(return_value=messages),
            ),
            patch(
                "api.routes.dialogue_session.dialogue_message_image_repository.find_by_session_id",
                new=AsyncMock(return_value=[]),
            ),
        ):
            result = await get_session_messages(session_id=session_id, current_user_id=_USER_ID, db=MagicMock())

        assert result.messages[0].intake_answers is not None
        assert result.messages[0].intake_answers.source == ["入門書"]
        assert result.messages[1].intake_answers is None

    async def test_returns_the_topic_correction_card_and_answer(self) -> None:
        session_id = uuid4()
        session = _make_session(session_id=session_id)
        card = json.dumps({"previous_topic": "この仕組み", "new_topic": "Linuxの仕組み"})
        messages = [
            _make_message("assistant", "変更しますか？", 4, topic_correction_card=card),
            _make_message("user", "はい、トピックを変更する", 5, topic_correction_answer="accept"),
            _make_message("assistant", "切り替えました", 6),
        ]
        with (
            patch(
                "api.routes.dialogue_session.dialogue_session_repository.find_by_id",
                new=AsyncMock(return_value=session),
            ),
            patch(
                "api.routes.dialogue_session.dialogue_message_repository.find_by_session_id",
                new=AsyncMock(return_value=messages),
            ),
            patch(
                "api.routes.dialogue_session.dialogue_message_image_repository.find_by_session_id",
                new=AsyncMock(return_value=[]),
            ),
        ):
            result = await get_session_messages(session_id=session_id, current_user_id=_USER_ID, db=MagicMock())

        assert result.messages[0].topic_correction_card is not None
        assert result.messages[0].topic_correction_card.new_topic == "Linuxの仕組み"
        assert result.messages[1].topic_correction_answer == "accept"
        assert result.messages[2].topic_correction_card is None
        assert result.messages[2].topic_correction_answer is None


class TestGetSessionImage:
    async def test_sets_nosniff_header_and_content_type(self) -> None:
        session_id = uuid4()
        image_id = uuid4()
        mock_db = MagicMock()
        fake_storage = MagicMock()
        fake_storage.get = AsyncMock(return_value=b"image-bytes")

        with (
            patch(
                "api.routes.dialogue_session.dialogue_session_repository.find_by_id",
                new=AsyncMock(return_value=_make_session(session_id=session_id)),
            ),
            patch(
                "api.routes.dialogue_session.dialogue_message_image_repository.find_in_session",
                new=AsyncMock(return_value={"storage_key": "k", "mime_type": "image/png"}),
            ),
            patch("api.routes.dialogue_session.get_storage", return_value=fake_storage),
        ):
            result = await get_session_image(
                session_id=session_id, image_id=image_id, current_user_id=_USER_ID, db=mock_db
            )

        assert result.headers["x-content-type-options"] == "nosniff"
        assert result.media_type == "image/png"
        assert result.body == b"image-bytes"

    async def test_raises_404_when_image_not_found(self) -> None:
        mock_db = MagicMock()

        with (
            patch(
                "api.routes.dialogue_session.dialogue_session_repository.find_by_id",
                new=AsyncMock(return_value=_make_session()),
            ),
            patch(
                "api.routes.dialogue_session.dialogue_message_image_repository.find_in_session",
                new=AsyncMock(return_value=None),
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_session_image(session_id=uuid4(), image_id=uuid4(), current_user_id=_USER_ID, db=mock_db)

        assert exc_info.value.status_code == 404
