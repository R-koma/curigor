import hashlib
from typing import Any

import pytest

from graph.prompts._base import DETAILED_STRUCTURE_RULES
from graph.prompts.explore import EXPLORE_BRIEF_RULES
from graph.prompts.side_question import (
    LEARNING_SIDE_RULES,
    _fingerprint_source,
    build_side_question_prompt,
    format_side_questions_for_context,
)


def _thread(quote: str, question: str, answer: str) -> dict[str, Any]:
    return {
        "quote": quote,
        "messages": [{"role": "user", "content": question}, {"role": "assistant", "content": answer}],
    }


def test_prompt_contains_anchor_text_quote_and_ancestors() -> None:
    prompt = build_side_question_prompt(
        session_type="explore",
        topic="データベースのインデックス",
        anchor_text="索引は B木 で管理される",
        quote="B木",
        recent_messages="ユーザー: インデックスとは\nAI: 索引です",
        ancestors="選んだ箇所: 「索引」\nユーザー: 索引とは？\nAI: 行の位置を指す一覧",
        other_side_questions="",
    )

    assert "索引は B木 で管理される" in prompt
    assert "「B木」" in prompt
    assert "行の位置を指す一覧" in prompt
    assert "データベースのインデックス" in prompt
    assert "{" not in prompt.replace("{{", "")


def test_side_question_keeps_the_brief_rules() -> None:
    prompt = build_side_question_prompt(
        session_type="explore",
        topic="T",
        anchor_text="A",
        quote="Q",
        recent_messages="",
        ancestors="",
        other_side_questions="",
    )

    assert EXPLORE_BRIEF_RULES in prompt
    assert "長い講義にしない" in prompt
    assert DETAILED_STRUCTURE_RULES not in prompt


def test_explore_prompt_with_quote_is_unchanged() -> None:
    prompt = build_side_question_prompt(
        session_type="explore",
        topic="T",
        anchor_text="A",
        quote="Q",
        recent_messages="M",
        ancestors="",
        other_side_questions="",
    )

    assert hashlib.sha256(prompt.encode()).hexdigest() == (
        "5c8be3a51351ccca0c84b038f64a93ecd8ed7b586545d1c7def576ca208f75e5"
    )


def test_learning_prompt_answers_without_asking_back() -> None:
    prompt = build_side_question_prompt(
        session_type="learning",
        topic="T",
        anchor_text="A",
        quote="Q",
        recent_messages="M",
        ancestors="",
        other_side_questions="",
    )

    assert "自分の言葉で説明する練習" in prompt
    assert "理解を確かめる問い" in prompt
    assert "2〜6文で" not in prompt
    assert "まったく知らない" not in prompt
    assert "「Q」" in prompt


@pytest.mark.parametrize("session_type", ["explore", "learning"])
def test_prompt_without_quote_has_no_passage_sections(session_type: str) -> None:
    prompt = build_side_question_prompt(
        session_type=session_type,
        topic="T",
        anchor_text="A",
        quote="",
        recent_messages="M",
        ancestors="",
        other_side_questions="",
    )

    assert "## 選んだ箇所" not in prompt
    assert "「」" not in prompt
    assert "選んだ箇所" not in prompt
    assert "{" not in prompt.replace("{{", "")


def test_fingerprint_covers_learning_rules() -> None:
    assert LEARNING_SIDE_RULES in _fingerprint_source()


def test_context_format_truncates_answers_to_200_chars_and_respects_max_chars() -> None:
    long_answer = "あ" * 500
    threads = [_thread("古い", "古い質問", "古い答え"), _thread("索引", "索引とは", long_answer)]

    full = format_side_questions_for_context(threads, max_chars=10_000)
    assert "「古い」" in full
    assert "あ" * 200 + "…" in full
    assert "あ" * 201 not in full
    assert full.index("「古い」") < full.index("「索引」")

    newest_only = format_side_questions_for_context(threads, max_chars=len(full) - 5)
    assert "「索引」" in newest_only
    assert "「古い」" not in newest_only

    assert format_side_questions_for_context(threads, max_chars=10) == ""
    assert format_side_questions_for_context([], max_chars=4000) == ""


def test_context_format_keeps_older_threads_when_the_newest_question_is_long() -> None:
    threads = [_thread("古い", "古い質問", "古い答え"), _thread("索引", "長い質問" * 2000, "答え")]

    text = format_side_questions_for_context(threads, max_chars=4000)

    assert "「古い」" in text
    assert "「索引」" in text
    assert "長い質問" * 75 + "…" in text
    assert "長い質問" * 76 not in text


def test_context_format_skips_a_thread_that_does_not_fit_and_keeps_older_ones() -> None:
    small = _thread("古い", "古い質問", "古い答え")
    large = _thread("索引" * 100, "質問", "あ" * 500)

    text = format_side_questions_for_context([small, large], max_chars=100)

    assert "「古い」" in text
    assert "索引索引" not in text
