from graph.prompts.intake import INTAKE_MAX_TURNS, build_intake_extraction_prompt, build_intake_prompt


class TestBuildIntakePrompt:
    def test_topic_is_not_treated_as_a_user_statement(self) -> None:
        rendered = build_intake_prompt(
            topic="システムコール", purpose="", source="", prior_knowledge="", recent_messages=""
        )
        assert "UI 入力値" in rendered

    def test_unanswered_fields_are_marked(self) -> None:
        rendered = build_intake_prompt(topic="キュー", purpose="", source="", prior_knowledge="", recent_messages="")
        assert rendered.count("未回答") == 3

    def test_known_fields_are_interpolated(self) -> None:
        rendered = build_intake_prompt(
            topic="キュー", purpose="面接対策", source="", prior_knowledge="", recent_messages="ユーザー: hi"
        )
        assert "面接対策" in rendered
        assert "ユーザー: hi" in rendered

    def test_empty_recent_messages_uses_placeholder(self) -> None:
        rendered = build_intake_prompt(topic="キュー", purpose="", source="", prior_knowledge="", recent_messages="")
        assert "（まだなし）" in rendered


class TestBuildIntakeExtractionPrompt:
    def test_interpolates_topic_and_history(self) -> None:
        rendered = build_intake_extraction_prompt(
            topic="キュー", purpose="", source="", prior_knowledge="", recent_messages="ユーザー: 面接対策です"
        )
        assert "キュー" in rendered
        assert "面接対策です" in rendered


def test_intake_max_turns_is_small() -> None:
    assert 1 <= INTAKE_MAX_TURNS <= 5


def test_intake_card_prompt_embeds_utterance_verbatim() -> None:
    from graph.prompts.intake import build_intake_card_prompt

    rendered = build_intake_card_prompt(utterance="仕事でReactのフックを使うので学びたい")

    assert "仕事でReactのフックを使うので学びたい" in rendered
    assert "{utterance}" not in rendered
