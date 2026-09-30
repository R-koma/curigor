from graph.prompts.intake import build_intake_extraction_prompt


class TestBuildIntakeExtractionPrompt:
    def test_interpolates_topic_and_history(self) -> None:
        rendered = build_intake_extraction_prompt(
            topic="キュー", purpose="", source="", prior_knowledge="", recent_messages="ユーザー: 面接対策です"
        )
        assert "キュー" in rendered
        assert "面接対策です" in rendered


def test_intake_card_prompt_embeds_utterance_verbatim() -> None:
    from graph.prompts.intake import build_intake_card_prompt

    rendered = build_intake_card_prompt(utterance="仕事でReactのフックを使うので学びたい")

    assert "仕事でReactのフックを使うので学びたい" in rendered
    assert "{utterance}" not in rendered
