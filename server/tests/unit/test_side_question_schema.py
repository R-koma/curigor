from uuid import uuid4

import pytest
from pydantic import ValidationError

from schemas.side_question import SideQuestionCreate


def test_create_without_quote_takes_no_anchor() -> None:
    body = SideQuestionCreate(content="なぜ？")

    assert body.quote == ""
    assert body.occurrence == 0
    assert body.anchor_message_id is None and body.anchor_side_message_id is None
    with pytest.raises(ValidationError):
        SideQuestionCreate(content="なぜ？", anchor_message_id=uuid4())
    with pytest.raises(ValidationError):
        SideQuestionCreate(content="なぜ？", anchor_side_message_id=uuid4())


def test_create_with_quote_takes_exactly_one_anchor() -> None:
    SideQuestionCreate(content="なぜ？", quote="索引", anchor_message_id=uuid4())
    with pytest.raises(ValidationError):
        SideQuestionCreate(content="なぜ？", quote="索引")
    with pytest.raises(ValidationError):
        SideQuestionCreate(content="なぜ？", quote="索引", anchor_message_id=uuid4(), anchor_side_message_id=uuid4())
