import pytest

from graph.prompts import explore as explore_prompts
from graph.prompts.explore import (
    EXPLORE_PROMPT_FINGERPRINT,
    build_explore_answers_prompt,
    build_explore_dialogue_prompt,
    build_explore_memo_organize_prompt,
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
    assert "読み方が示されている用語だけ" in build_explore_terms_prompt(topic="二分探索", text="計算量とは")


def test_term_extraction_skips_words_from_examples_and_expansions() -> None:
    prompts = [
        build_explore_terms_prompt(topic="MECE", text="顧客を個人／法人に分ける"),
        build_explore_turn_analysis_prompt(topic="MECE", recent_messages="ユーザー: 例を出して"),
    ]

    for prompt in prompts:
        assert "具体例や例え話の中で使っただけの言葉" in prompt
        assert "略語の正式名称" in prompt
    assert "「MECE」を学んでいます" in prompts[0]


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


def test_organize_memo_prompt_numbers_questions_and_terms_and_lists_aspect_ids() -> None:
    prompt = build_explore_memo_organize_prompt(
        topic="二分探索",
        aspects=[
            {
                "id": "asp-1",
                "name": "比較",
                "is_core": True,
                "defined_question": "d",
                "reasoned_question": "r",
                "applied_question": "a",
            }
        ],
        pairs=[("二分探索とは", "半分ずつ探す")],
        terms=[{"term": "計算量", "reading": "", "meaning": "手間の目安"}],
    )

    assert "[0] 質問: 二分探索とは" in prompt
    assert "[0] 計算量: 手間の目安" in prompt
    assert "- asp-1: 比較" in prompt


def test_organize_memo_prompt_states_the_mandatory_rules() -> None:
    prompt = build_explore_memo_organize_prompt(topic="二分探索", aspects=[], pairs=[], terms=[])

    assert "aspect_id は、上の `id` をそのまま写す" in prompt
    assert "question_indices は「疑問と回答」の [] の数字" in prompt
    assert "term_indices は「用語」の [] の数字" in prompt
    assert "最も当たる観点一つにだけ入れる" in prompt
    assert "どこにも入れない" in prompt
    assert "書かれていない知識を足さない" in prompt
    assert "2〜4文" in prompt
    assert "一行要約" not in prompt


def test_explore_fingerprint_covers_the_organize_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    before = explore_prompts._explore_prompt_fingerprint()
    monkeypatch.setattr(explore_prompts, "EXPLORE_MEMO_ORGANIZE_PROMPT", "changed")

    assert explore_prompts._explore_prompt_fingerprint() != before
