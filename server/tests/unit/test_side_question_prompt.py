from typing import Any

from graph.prompts.side_question import build_side_question_prompt, format_side_questions_for_context


def _thread(quote: str, question: str, answer: str) -> dict[str, Any]:
    return {
        "quote": quote,
        "messages": [{"role": "user", "content": question}, {"role": "assistant", "content": answer}],
    }


def test_prompt_contains_anchor_text_quote_and_ancestors() -> None:
    prompt = build_side_question_prompt(
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
