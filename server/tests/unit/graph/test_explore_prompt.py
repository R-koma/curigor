from graph.explore import overview_aspects
from graph.prompts.explore import (
    EXPLORE_PROMPT_FINGERPRINT,
    build_explore_answers_prompt,
    build_explore_dialogue_prompt,
    build_explore_turn_analysis_prompt,
)
from graph.state import DepthMapState

MAP: DepthMapState = {
    "topic": "二分探索",
    "aspects": [
        {
            "id": "比較",
            "name": "真ん中との比較",
            "is_core": True,
            "defined_question": "真ん中と比べるとは",
            "reasoned_question": "なぜ半分を捨てられるか",
            "applied_question": "どこで使うか",
        }
    ],
}


def _dialogue(**overrides: object) -> str:
    kwargs: dict[str, object] = {
        "topic": "二分探索",
        "source": "",
        "overview": overview_aspects(MAP, {}, []),
        "target": MAP["aspects"][0],
        "intent": "next",
        "wrap_up": False,
        "end_offered": False,
        "recent_messages": "ユーザー: 最初から",
    }
    kwargs.update(overrides)
    return build_explore_dialogue_prompt(**kwargs)  # type: ignore[arg-type]


def test_explaining_turn_targets_one_aspect_and_its_core_questions() -> None:
    prompt = _dialogue()

    assert "真ん中との比較" in prompt
    assert "なぜ半分を捨てられるか" in prompt
    assert "1回の応答で説明する概念は1つ" in prompt


def test_question_turn_answers_without_moving_on() -> None:
    prompt = _dialogue(intent="question")

    assert "質問に答える" in prompt
    assert "次の観点へ進まない" in prompt


def test_material_turn_explains_the_shown_passage() -> None:
    assert "示した教材" in _dialogue(intent="material", source="入門書")


def test_wrap_up_and_end_sections_only_when_asked() -> None:
    assert "学習メモ" not in _dialogue()
    assert "学習メモ" in _dialogue(wrap_up=True)
    assert "新しい概念を説明しない" in _dialogue(intent="end_session", end_offered=True)


def test_turn_analysis_lists_aspects_with_explained_marks_apart_from_names() -> None:
    prompt = build_explore_turn_analysis_prompt(
        topic="二分探索", depth_map=MAP, explained=["比較"], recent_messages="ユーザー: 次へ"
    )

    assert "- 比較 | 真ん中との比較 | 中核 | 説明済み" in prompt


def test_answers_prompt_numbers_each_pair() -> None:
    prompt = build_explore_answers_prompt(pairs=[("なぜ並べるのか", "半分を捨てる判断に必要だから")])

    assert "[0] 質問: なぜ並べるのか" in prompt
    assert "回答: 半分を捨てる判断に必要だから" in prompt


def test_fingerprint_is_a_short_hash() -> None:
    assert len(EXPLORE_PROMPT_FINGERPRINT) == 12
