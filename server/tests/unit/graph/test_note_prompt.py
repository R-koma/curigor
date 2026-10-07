from graph.prompts import APPEND_REVIEW_PROMPT, GENERATE_NOTE_PROMPT, UPDATE_NOTE_PROMPT


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
