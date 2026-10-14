from graph.prompts.explore import (
    EXPLORE_PROMPT_FINGERPRINT,
    build_explore_answers_prompt,
    build_explore_dialogue_prompt,
    build_explore_teachback_map_prompt,
    build_explore_terms_prompt,
    build_explore_turn_analysis_prompt,
)


def _dialogue(**overrides: object) -> str:
    kwargs: dict[str, object] = {
        "topic": "二分探索",
        "intent": "question",
        "wrap_up": False,
        "end_offered": False,
        "recent_messages": "ユーザー: 二分探索って何？",
    }
    kwargs.update(overrides)
    return build_explore_dialogue_prompt(**kwargs)  # type: ignore[arg-type]


def test_answers_questions_and_aims_at_deeper_understanding() -> None:
    prompt = _dialogue()

    assert "疑問に答える" in prompt
    assert "つまずいている" in prompt
    assert "二分探索って何？" in prompt


def test_never_adds_readings_unless_asked() -> None:
    prompt = _dialogue()

    assert "読み仮名を添えない" in prompt
    assert "読み方を尋ねた" in prompt
    assert "「用語（ようご）」" not in prompt


def test_does_not_assert_what_it_is_unsure_of() -> None:
    prompt = _dialogue()

    assert "推測で言い切らない" in prompt
    assert "公式の資料で確かめる" in prompt


def test_answers_an_overview_only_when_asked() -> None:
    assert "全体像を尋ねられたら" in _dialogue()


def test_material_turn_explains_the_shown_passage() -> None:
    assert "示した教材" in _dialogue(intent="material")


def test_understood_turn_asks_for_remaining_questions_without_new_concepts() -> None:
    prompt = _dialogue(intent="understood")

    assert "新しい概念を説明しない" in prompt
    assert "気になっている点" in prompt
    assert "学習メモ" not in prompt


def test_wrap_up_proposes_moving_on_to_explaining() -> None:
    prompt = _dialogue(intent="understood", wrap_up=True)

    assert "自分の言葉で説明してみる" in prompt
    assert "学習メモ" in prompt


def test_end_section_only_when_the_end_is_offered() -> None:
    assert "終了ボタン" in _dialogue(intent="end_session", end_offered=True)


def test_turn_analysis_has_no_aspect_table_and_asks_for_the_topic() -> None:
    prompt = build_explore_turn_analysis_prompt(topic="二分探索", recent_messages="ユーザー: わかった")

    assert "`topic`" in prompt
    assert "understood" in prompt
    assert "観点" not in prompt
    assert "AI の発言が無い最初のターンだけ" in prompt


def test_term_readings_only_when_shown() -> None:
    assert "読み方が示されている用語だけ" in build_explore_terms_prompt(text="計算量とは")


def test_answers_prompt_numbers_each_pair() -> None:
    prompt = build_explore_answers_prompt(pairs=[("なぜ並べるのか", "半分を捨てる判断に必要だから")])

    assert "[0] 質問: なぜ並べるのか" in prompt


def test_teachback_map_uses_only_what_was_taught() -> None:
    prompt = build_explore_teachback_map_prompt(
        topic="二分探索",
        pairs=[("なぜ並べるのか", "半分を捨てる判断に必要だから")],
        terms=[{"term": "計算量", "reading": "", "meaning": "手間の目安"}],
    )

    assert "なぜ並べるのか" in prompt
    assert "- 計算量: 手間の目安" in prompt
    assert "会話で扱っていない内容を観点にしない" in prompt
    assert "答えそのものを書かない" in prompt
    assert "スキーマの説明（3〜7個）ではなく、この指示の2〜5個と「会話で扱った内容だけ」を優先する" in prompt


def test_fingerprint_is_a_short_hash() -> None:
    assert len(EXPLORE_PROMPT_FINGERPRINT) == 12
