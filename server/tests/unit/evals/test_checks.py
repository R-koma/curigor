import pytest

from evals.checks import (
    check_fingerprint,
    contains_diagram,
    contains_generic_prompt_phrase,
    contains_unescaped_price,
    contains_unfenced_code,
    contains_unformatted_math,
    repeats_previous_opening,
    run_check,
)


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


FENCED_PYTHON = "例です。\n```python\ndef add(a, b):\n    return a + b\n```\nどう動きますか？"


class TestContainsUnfencedCode:
    @pytest.mark.parametrize(
        "output",
        [
            "次の関数を見てください。\ndef add(a, b):\n    return a + b\nこれは何を返しますか？",
            "次を実行します。\nSELECT name FROM users;\n何が返りますか？",
            "例えば\n  if (x > 0) {\n    count++;\n  }\nのように書きます。",
        ],
    )
    def test_detects_code_outside_a_fence(self, output: str) -> None:
        assert contains_unfenced_code(output).holds is True

    @pytest.mark.parametrize(
        "output",
        [
            FENCED_PYTHON,
            "`def` で関数を定義します。`return` は何を返しますか？",
            "return 文は値を返します。関数の外から何が見えますか？",
            "- 箇条書きです\n  - 入れ子の項目:\n  - もう一つ:",
            "```python\ndef f():",
            "1. 手順:\n   詳細 (a)\n   詳細 (b)",
            "  補足 (1)\n  補足 (2)",
            "1) まず確かめる:\n2) 次に比べる:",
        ],
    )
    def test_ignores_fenced_inline_and_prose(self, output: str) -> None:
        assert contains_unfenced_code(output).holds is False


class TestContainsUnformattedMath:
    @pytest.mark.parametrize(
        "output",
        [
            "解の公式は x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a} です。",
            "x^2 + 1 = 0 の解は？",
            "数列 a_n の和は？",
            "a_{n+1} は？",
        ],
    )
    def test_detects_math_outside_dollars(self, output: str) -> None:
        assert contains_unformatted_math(output).holds is True

    @pytest.mark.parametrize(
        "output",
        [
            "解の公式は $x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$ です。",
            "$$\nx^2 + 1 = 0\n$$\nの解は？",
            "変数 max_value と snake_case の名前を使います。",
            "`x^2` をコードで書くと `x**2` です。",
            "速さは 10 m/s です。",
        ],
    )
    def test_ignores_formatted_math_and_identifiers(self, output: str) -> None:
        assert contains_unformatted_math(output).holds is False


class TestContainsUnescapedPrice:
    @pytest.mark.parametrize(
        "output",
        [
            "料金は $5 と $10 の 2 種類です。",
            "月額 $20 です。",
            "$5、税込みで $6 です。",
        ],
    )
    def test_detects_a_bare_dollar_price(self, output: str) -> None:
        assert contains_unescaped_price(output).holds is True

    @pytest.mark.parametrize(
        "output",
        [
            "料金は \\$5 と \\$10 の 2 種類です。",
            "$2 + 3 = 5$ を確かめましょう。",
            "$10$ 個です。",
            "`echo $1` で引数を表示します。",
            "```bash\necho $1 $2\n```",
        ],
    )
    def test_ignores_escaped_prices_math_and_code(self, output: str) -> None:
        assert contains_unescaped_price(output).holds is False


class TestContainsDiagram:
    def test_detects_a_mermaid_block(self) -> None:
        assert contains_diagram("流れです。\n```mermaid\ngraph TD\n  A --> B\n```").holds is True

    def test_ignores_other_code_blocks(self) -> None:
        assert contains_diagram(FENCED_PYTHON).holds is False


class TestFormattingChecksAreRegistered:
    @pytest.mark.parametrize(
        "name",
        ["contains_unfenced_code", "contains_unformatted_math", "contains_unescaped_price", "contains_diagram"],
    )
    def test_dispatches_by_name(self, name: str) -> None:
        assert run_check(name, "ただの文です。").holds is False
        assert len(check_fingerprint(name)) == 12
