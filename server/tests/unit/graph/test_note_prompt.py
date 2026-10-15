import pytest

from graph.prompts import APPEND_REVIEW_PROMPT, GENERATE_NOTE_PROMPT, UPDATE_NOTE_PROMPT, collection, note


def test_note_prompt_places_ai_supplements_between_key_points_and_open_questions() -> None:
    key_points = GENERATE_NOTE_PROMPT.index("`## 重要なポイント`")
    supplements = GENERATE_NOTE_PROMPT.index("`## AIの補足`")
    open_questions = GENERATE_NOTE_PROMPT.index("「まだ曖昧な点」は blockquote callout")
    assert key_points < supplements < open_questions


def test_note_prompt_keeps_terms_the_learner_did_not_use_out_of_what_they_learned() -> None:
    assert "用語名を「学んだこと」「重要なポイント」に書かない" in GENERATE_NOTE_PROMPT
    assert "AI が問いを出しただけでユーザーが答えていない内容" in GENERATE_NOTE_PROMPT


def test_insufficient_dialogue_is_not_filled_with_ai_supplements() -> None:
    assert "対話不十分と判定した場合も「AIの補足」で埋めない" in GENERATE_NOTE_PROMPT


def test_note_prompt_example_does_not_use_the_verification_topics() -> None:
    assert "システムコール" not in GENERATE_NOTE_PROMPT
    assert "ハンドシェイク" not in GENERATE_NOTE_PROMPT


def _format_update() -> str:
    return UPDATE_NOTE_PROMPT.format(topic="T", summary="S", content="C", conversation_history="H")


def test_update_prompt_keeps_ai_supplements_in_the_structure() -> None:
    assert "`## AIの補足`" in _format_update()


def test_update_prompt_moves_supplements_the_learner_explained() -> None:
    assert "その項目を「AIの補足」から外し、「学んだこと」へ移す" in _format_update()


def test_append_prompt_does_not_add_ai_explanations_as_understanding() -> None:
    text = APPEND_REVIEW_PROMPT.format(topic="T", content="C", conversation_history="H")
    assert "AI が示した用語・定義は、ユーザーが自分の言葉で説明していなければ追記しない" in text


def test_mechanism_explained_without_the_term_is_not_insufficient_dialogue() -> None:
    assert "用語を使わなくても、仕組みや内容を自分の言葉で説明していれば対話不十分としない" in GENERATE_NOTE_PROMPT


def test_unanswered_questions_rule_does_not_apply_to_insufficient_dialogue() -> None:
    assert "対話不十分と判定した場合を除き、AI が問いを出しただけで" in GENERATE_NOTE_PROMPT


def test_category_prompt_lists_existing_categories_as_bullets() -> None:
    assert "- 数学\n- 英語" in note.build_category_prompt(["数学", "英語"])


def test_category_prompt_without_categories_says_there_are_none() -> None:
    assert note.NO_CATEGORIES_PLACEHOLDER in note.build_category_prompt([])


class TestNotePromptFingerprint:
    def test_is_a_12_digit_hex(self) -> None:
        for value in (note.NOTE_PROMPT_FINGERPRINT, note.REVIEW_NOTE_PROMPT_FINGERPRINT):
            assert len(value) == 12
            int(value, 16)

    def test_matches_the_function(self) -> None:
        assert note.NOTE_PROMPT_FINGERPRINT == note._note_prompt_fingerprint()
        assert note.REVIEW_NOTE_PROMPT_FINGERPRINT == note._review_note_prompt_fingerprint()

    def test_generation_and_review_differ(self) -> None:
        assert note.NOTE_PROMPT_FINGERPRINT != note.REVIEW_NOTE_PROMPT_FINGERPRINT

    @pytest.mark.parametrize(
        "name", ["GENERATE_NOTE_PROMPT", "GENERATE_CATEGORY_PROMPT", "GENERATE_ASPECT_MAP_PROMPT"]
    )
    def test_note_fingerprint_tracks_the_generation_prompts(self, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
        before = note._note_prompt_fingerprint()
        monkeypatch.setattr(note, name, getattr(note, name) + "\n追記")
        assert note._note_prompt_fingerprint() != before

    def test_note_fingerprint_tracks_the_category_placeholder(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = note._note_prompt_fingerprint()
        monkeypatch.setattr(note, "NO_CATEGORIES_PLACEHOLDER", note.NO_CATEGORIES_PLACEHOLDER + "追記")
        assert note._note_prompt_fingerprint() != before

    def test_note_fingerprint_tracks_the_collection_prompt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = note._note_prompt_fingerprint()
        monkeypatch.setattr(
            collection, "COLLECTION_SUGGESTION_PROMPT", collection.COLLECTION_SUGGESTION_PROMPT + "\n追記"
        )
        assert note._note_prompt_fingerprint() != before

    @pytest.mark.parametrize("name", ["UPDATE_NOTE_PROMPT", "APPEND_REVIEW_PROMPT"])
    def test_review_fingerprint_tracks_the_review_prompts(self, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
        before = note._review_note_prompt_fingerprint()
        monkeypatch.setattr(note, name, getattr(note, name) + "\n追記")
        assert note._review_note_prompt_fingerprint() != before

    def test_review_fingerprint_ignores_the_generation_prompt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = note._review_note_prompt_fingerprint()
        monkeypatch.setattr(note, "GENERATE_NOTE_PROMPT", note.GENERATE_NOTE_PROMPT + "\n追記")
        assert note._review_note_prompt_fingerprint() == before
