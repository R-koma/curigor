from graph.prompts.feedback import GENERATE_FEEDBACK_PROMPT, build_aspect_section
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
