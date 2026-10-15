import pytest

from graph.prompts import explore, feedback, map_question, note, question, review, synthesis
from graph.prompts._base import (
    DIAGRAM_RULE,
    FORMATTING_RULES,
    NO_DIAGRAM_RULE,
    RECORD_RULE,
    inject_formatting,
)


class TestInjectFormatting:
    def test_replaces_the_placeholder_with_the_rules(self) -> None:
        prompt = inject_formatting("前\n{{FORMATTING}}\n後")

        assert "{{FORMATTING}}" not in prompt
        assert FORMATTING_RULES in prompt
        assert prompt.startswith("前\n## 表記\n")
        assert prompt.endswith("\n後")

    def test_forbids_diagrams_by_default(self) -> None:
        prompt = inject_formatting("{{FORMATTING}}")

        assert NO_DIAGRAM_RULE in prompt
        assert DIAGRAM_RULE not in prompt

    def test_allows_one_diagram_when_asked(self) -> None:
        prompt = inject_formatting("{{FORMATTING}}", diagrams=True)

        assert DIAGRAM_RULE in prompt
        assert NO_DIAGRAM_RULE not in prompt

    def test_adds_the_record_rule_only_for_records(self) -> None:
        assert RECORD_RULE not in inject_formatting("{{FORMATTING}}")
        assert RECORD_RULE in inject_formatting("{{FORMATTING}}", record=True)

    def test_survives_str_format(self) -> None:
        prompt = inject_formatting("{topic}\n{{FORMATTING}}", diagrams=True, record=True)

        assert prompt.format(topic="二次方程式").startswith("二次方程式\n## 表記")

    def test_quotes_the_learners_code_and_math_inside_the_usual_markup(self) -> None:
        assert "表記を変えずに" not in FORMATTING_RULES
        assert "中身を変えずに" in FORMATTING_RULES
        assert "$O(n^2)$" in FORMATTING_RULES

    def test_states_each_rule(self) -> None:
        assert "```言語名" in FORMATTING_RULES
        assert "$…$" in FORMATTING_RULES
        assert "$$…$$" in FORMATTING_RULES
        assert "\\$5" in FORMATTING_RULES
        assert "```mermaid" in DIAGRAM_RULE


DIALOGUE_PROMPTS = {
    "question": question.QUESTION_PROMPT_BASE,
    "map_question": map_question.MAP_QUESTION_PROMPT_BASE,
    "review": review.REVIEW_SYSTEM_PROMPT,
    "synthesis_opening": synthesis.SYNTHESIS_OPENING_PROMPT,
    "synthesis_dialogue": synthesis.SYNTHESIS_DIALOGUE_PROMPT,
}

RECORD_PROMPTS = {
    "explore_answers": explore.EXPLORE_ANSWERS_PROMPT,
    "synthesis_draft": synthesis.SYNTHESIS_DRAFT_PROMPT,
    "generate_note": note.GENERATE_NOTE_PROMPT,
    "update_note": note.UPDATE_NOTE_PROMPT,
    "append_review": note.APPEND_REVIEW_PROMPT,
    "generate_feedback": feedback.GENERATE_FEEDBACK_PROMPT,
}


class TestPromptsCarryTheRules:
    @pytest.mark.parametrize("name", sorted(DIALOGUE_PROMPTS))
    def test_dialogue_prompts_forbid_diagrams(self, name: str) -> None:
        prompt = DIALOGUE_PROMPTS[name]
        assert FORMATTING_RULES in prompt
        assert NO_DIAGRAM_RULE in prompt
        assert RECORD_RULE not in prompt

    def test_only_the_explore_dialogue_allows_a_diagram(self) -> None:
        assert FORMATTING_RULES in explore.EXPLORE_DIALOGUE_PROMPT
        assert DIAGRAM_RULE in explore.EXPLORE_DIALOGUE_PROMPT
        for prompt in [*DIALOGUE_PROMPTS.values(), *RECORD_PROMPTS.values()]:
            assert DIAGRAM_RULE not in prompt

    @pytest.mark.parametrize("name", sorted(RECORD_PROMPTS))
    def test_record_prompts_keep_the_learners_code_and_math(self, name: str) -> None:
        prompt = RECORD_PROMPTS[name]
        assert FORMATTING_RULES in prompt
        assert RECORD_RULE in prompt

    def test_no_placeholder_is_left(self) -> None:
        for prompt in [*DIALOGUE_PROMPTS.values(), *RECORD_PROMPTS.values(), explore.EXPLORE_DIALOGUE_PROMPT]:
            assert "{{FORMATTING}}" not in prompt
