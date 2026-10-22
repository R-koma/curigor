import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from core import config
from services.transcript_format import TranscriptFormatError, format_transcript, is_deletion_only


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        ("えーと、スタックは。後入れ先出しです。", "スタックは後入れ先出しです。", True),
        ("スタックは後入れ先出しです", "スタックは、後入れ先出しです。", True),
        ("スタックは後入れ先出しです。", "スタックは先入れ先出しです。", False),
        ("スタックは後入れ先出しです。", "スタックは後入れ先出しです。つまり LIFO です。", False),
        ("スタックは後入れ先出しで、配列で作れます。", "スタックは後入れ先出しです。", False),
        ("その値を返します。", "値を返します。", False),
        ("その他の方法です。", "他の方法です。", False),
        ("その、値を返します。", "値を返します。", True),
        ("その API を呼ぶ。", "API を呼ぶ。", False),
        ("その，値です。", "値です。", True),
    ],
)
def test_is_deletion_only(before: str, after: str, expected: bool) -> None:
    assert is_deletion_only(before, after) is expected


async def test_format_transcript_returns_formatted_text_for_a_deletion_only_edit() -> None:
    reply = AIMessage("スタックは、後入れ先出しです。")
    with patch("services.transcript_format.llm.ainvoke", new=AsyncMock(return_value=reply)):
        result = await format_transcript("スタックは。後入れ先出しです", session_id=uuid4(), user_id="u")

    assert result == "スタックは、後入れ先出しです。"


async def test_format_transcript_returns_input_when_llm_rewrites() -> None:
    reply = AIMessage("スタックは先入れ先出しです。")
    with patch("services.transcript_format.llm.ainvoke", new=AsyncMock(return_value=reply)):
        result = await format_transcript("スタックは後入れ先出しです。", session_id=uuid4(), user_id="u")

    assert result == "スタックは後入れ先出しです。"


async def test_format_transcript_raises_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    async def slow(*args: object, **kwargs: object) -> AIMessage:
        await asyncio.sleep(1)
        return AIMessage("x")

    monkeypatch.setattr(config, "TRANSCRIPT_FORMAT_TIMEOUT_SECONDS", 0.01)
    with (
        patch("services.transcript_format.llm.ainvoke", new=slow),
        pytest.raises(TranscriptFormatError),
    ):
        await format_transcript("スタックです。", session_id=uuid4(), user_id="u")


async def test_format_transcript_raises_when_llm_fails() -> None:
    with (
        patch("services.transcript_format.llm.ainvoke", new=AsyncMock(side_effect=RuntimeError("boom"))),
        pytest.raises(TranscriptFormatError),
    ):
        await format_transcript("スタックです。", session_id=uuid4(), user_id="u")
