import pytest

from graph.prompts import depth_map, intake
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


class TestIntakePromptFingerprint:
    def test_is_stable(self) -> None:
        assert intake._intake_prompt_fingerprint() == intake._intake_prompt_fingerprint()
        assert intake.INTAKE_PROMPT_FINGERPRINT == intake._intake_prompt_fingerprint()
        assert len(intake.INTAKE_PROMPT_FINGERPRINT) == 12

    @pytest.mark.parametrize("name", ["INTAKE_CARD_PROMPT", "INTAKE_EXTRACTION_PROMPT", "LEARNING_KICKOFF_PROMPT"])
    def test_tracks_intake_prompt_text(self, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
        before = intake._intake_prompt_fingerprint()
        monkeypatch.setattr(intake, name, getattr(intake, name) + "\n追記")
        assert intake._intake_prompt_fingerprint() != before

    def test_tracks_the_depth_map_prompt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = intake._intake_prompt_fingerprint()
        monkeypatch.setattr(depth_map, "DEPTH_MAP_GENERATION_PROMPT", depth_map.DEPTH_MAP_GENERATION_PROMPT + "\n追記")
        assert intake._intake_prompt_fingerprint() != before

    def test_tracks_the_unanswered_placeholder(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = intake._intake_prompt_fingerprint()
        monkeypatch.setattr(intake, "_known", lambda value: value or "不明")
        assert intake._intake_prompt_fingerprint() != before
