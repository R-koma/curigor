from graph.prompts.analysis import ANALYZE_RESPONSE_PROMPT
from graph.prompts.feedback import (
    _SIDE_QUESTIONS_ANALYSIS_SECTION,
    _SIDE_SECTION_SCORING_RULE,
    GENERATE_FEEDBACK_PROMPT,
    _feedback_prompt_parts,
    build_analysis_prompt,
    build_aspect_section,
    build_scoring_prompt,
)
from tests.unit.graph.test_aspect_map import MAP


def test_aspect_section_lists_ids_with_indent() -> None:
    section = build_aspect_section(MAP)
    assert "- a1: 計算量" in section
    assert "  - a1-1: 最悪計算量" in section
    assert "    - a1-1-1: 対数" in section


def test_aspect_section_without_map_tells_to_leave_ids_empty() -> None:
    for value in (None, {"root": "x", "aspects": []}):
        section = build_aspect_section(value)
        assert "空文字" in section
        assert "- a1" not in section


def test_feedback_prompt_formats_with_aspect_section() -> None:
    text = GENERATE_FEEDBACK_PROMPT.format(topic="t", analysis="a", aspect_section="観点セクション")
    assert "観点セクション" in text


def test_feedback_prompt_does_not_credit_ai_supplements() -> None:
    text = GENERATE_FEEDBACK_PROMPT.format(topic="t", analysis="a", aspect_section="")
    assert "ノートの「AIの補足」は AI が示した内容であり、strengths の根拠にしない" in text


def test_analysis_prompt_is_unchanged_without_side_questions() -> None:
    assert build_analysis_prompt("T", "H", ()) == ANALYZE_RESPONSE_PROMPT.format(topic="T", conversation_history="H")


def test_analysis_prompt_lists_side_questions_after_the_history() -> None:
    prompt = build_analysis_prompt("T", "ユーザー: 索引は表です", ["索引とは？", "なぜ{速い}？"])

    assert "## 横の欄で質問したこと" in prompt
    assert "- 索引とは？\n- なぜ{速い}？" in prompt
    assert prompt.index("ユーザー: 索引は表です") < prompt.index("## 横の欄で質問したこと") < prompt.index("## タスク")
    assert "自分の言葉で説明できたこと・理解していることの根拠にしない" in prompt


def test_scoring_prompt_is_unchanged_without_the_section() -> None:
    assert build_scoring_prompt(topic="T", analysis="A", aspect_section="", note_text="トピック: T\n\nノート") == (
        GENERATE_FEEDBACK_PROMPT.format(topic="T", analysis="A", aspect_section="")
    )


def test_scoring_prompt_excludes_the_section_from_strengths() -> None:
    prompt = build_scoring_prompt(
        topic="T", analysis="A", aspect_section="", note_text="トピック: T\n\n## わからなかったこと\n- **Q**"
    )

    assert "ノートの「わからなかったこと」は、ユーザーが対話の途中で質問して教わった内容である" in prompt


def test_feedback_fingerprint_covers_the_new_rules() -> None:
    parts = _feedback_prompt_parts()

    assert _SIDE_QUESTIONS_ANALYSIS_SECTION in parts
    assert _SIDE_SECTION_SCORING_RULE in parts
