import pytest

from evals.checks import check_fingerprint, contains_generic_prompt_phrase, repeats_previous_opening, run_check


class TestContainsGenericPromptPhrase:
    def test_detects_known_phrase(self) -> None:
        result = contains_generic_prompt_phrase("さらに詳しく説明してみてください。")
        assert result.holds is True

    def test_no_match_returns_false(self) -> None:
        result = contains_generic_prompt_phrase("スループットについて、もう一度説明してもらえますか？")
        assert result.holds is False

    def test_detail_lists_matched_phrases(self) -> None:
        result = contains_generic_prompt_phrase("もう少し詳しく、さらに詳しく教えてください")
        assert "もう少し詳しく" in result.detail
        assert "さらに詳しく" in result.detail


def _history(*assistant_messages: str) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for content in assistant_messages:
        history.append({"role": "assistant", "content": content})
        history.append({"role": "user", "content": "わかりません"})
    return history


class TestRepeatsPreviousOpening:
    def test_detects_the_same_opening_as_a_recent_reply(self) -> None:
        history = _history("大丈夫ですよ。では基礎から考えましょう。")
        result = repeats_previous_opening("大丈夫ですよ。具体例を1つお話しします。", history)
        assert result.holds is True

    def test_a_different_opening_does_not_hold(self) -> None:
        history = _history("大丈夫ですよ。では基礎から考えましょう。")
        result = repeats_previous_opening("ここは迷いやすいところです。", history)
        assert result.holds is False

    def test_compares_up_to_the_first_comma(self) -> None:
        history = _history("良い整理ですね、では次に進みます。")
        result = repeats_previous_opening("良い整理ですね。もう一つ聞かせてください。", history)
        assert result.holds is True

    def test_ignores_short_openings(self) -> None:
        history = _history("では、次の例を見ましょう。")
        result = repeats_previous_opening("では、別の場面ではどうでしょうか？", history)
        assert result.holds is False

    def test_ignores_user_messages(self) -> None:
        history = [{"role": "user", "content": "大丈夫ですよ。わかります。"}]
        result = repeats_previous_opening("大丈夫ですよ。続けましょう。", history)
        assert result.holds is False

    def test_only_looks_at_the_last_three_replies(self) -> None:
        history = _history("大丈夫ですよ。", "一つ目です。", "二つ目です。", "三つ目です。")
        result = repeats_previous_opening("大丈夫ですよ。続けましょう。", history)
        assert result.holds is False


class TestRunCheck:
    def test_dispatches_by_name(self) -> None:
        result = run_check("contains_generic_prompt_phrase", "掘り下げてみませんか？")
        assert result.holds is True

    def test_unknown_check_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown deterministic check"):
            run_check("does_not_exist", "output")

    def test_passes_the_conversation_history_to_history_checks(self) -> None:
        history = [{"role": "assistant", "content": "なるほどですね。"}]
        result = run_check("repeats_previous_opening", "なるほどですね。次です。", history)
        assert result.holds is True

    def test_history_checks_can_be_fingerprinted(self) -> None:
        assert len(check_fingerprint("repeats_previous_opening")) == 12
