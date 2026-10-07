from graph.prompts import GENERATE_NOTE_PROMPT


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
