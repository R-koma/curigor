import pytest

from graph.output_schemas import ExploreIntent
from graph.prompts import explore, feedback, map_question, note, question, review, synthesis
from graph.prompts._base import (
    CHAT_STRUCTURE_RULES,
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

    def test_adds_the_chat_structure_rules_only_for_chat(self) -> None:
        assert CHAT_STRUCTURE_RULES not in inject_formatting("{{FORMATTING}}")
        assert CHAT_STRUCTURE_RULES in inject_formatting("{{FORMATTING}}", chat=True)

    def test_survives_str_format(self) -> None:
        prompt = inject_formatting("{topic}\n{{FORMATTING}}", diagrams=True, record=True, chat=True)

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

    def test_structures_only_long_explanations(self) -> None:
        assert "3 文以内" in CHAT_STRUCTURE_RULES
        assert "空行" in CHAT_STRUCTURE_RULES
        assert "箇条書き" in CHAT_STRUCTURE_RULES
        assert "番号リスト" in CHAT_STRUCTURE_RULES
        assert "**太字**" in CHAT_STRUCTURE_RULES
        assert "見出し" in CHAT_STRUCTURE_RULES


DIALOGUE_PROMPTS = {
    "question": question.QUESTION_PROMPT_BASE,
    "map_question": map_question.MAP_QUESTION_PROMPT_BASE,
    "review": review.REVIEW_SYSTEM_PROMPT,
    "synthesis_opening": synthesis.SYNTHESIS_OPENING_PROMPT,
    "synthesis_dialogue": synthesis.SYNTHESIS_DIALOGUE_PROMPT,
}

RECORD_PROMPTS = {
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

    @pytest.mark.parametrize("name", sorted(DIALOGUE_PROMPTS))
    def test_dialogue_prompts_structure_long_explanations(self, name: str) -> None:
        assert CHAT_STRUCTURE_RULES in DIALOGUE_PROMPTS[name]

    def test_records_and_memos_are_not_chat(self) -> None:
        for prompt in [
            *RECORD_PROMPTS.values(),
            explore.EXPLORE_ANSWERS_PROMPT,
            explore.EXPLORE_MEMO_ORGANIZE_PROMPT,
        ]:
            assert CHAT_STRUCTURE_RULES not in prompt

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

    def test_the_memo_answers_keep_the_answers_code_and_math(self) -> None:
        prompt = explore.EXPLORE_ANSWERS_PROMPT
        assert FORMATTING_RULES in prompt
        assert explore.ANSWER_RECORD_RULE in prompt
        assert RECORD_RULE not in prompt

    def test_record_rule_does_not_assume_sections(self) -> None:
        assert "節" not in RECORD_RULE

    def test_no_placeholder_is_left(self) -> None:
        for prompt in [*DIALOGUE_PROMPTS.values(), *RECORD_PROMPTS.values(), explore.EXPLORE_DIALOGUE_PROMPT]:
            assert "{{FORMATTING}}" not in prompt


def _explore_dialogue(intent: ExploreIntent, *, wrap_up: bool = False, end_offered: bool = False) -> str:
    return explore.build_explore_dialogue_prompt(
        topic="二分探索", intent=intent, wrap_up=wrap_up, end_offered=end_offered, recent_messages=""
    )


class TestExploreDiagrams:
    @pytest.mark.parametrize("intent", ["question", "understood"])
    def test_explore_turns_structure_long_explanations(self, intent: ExploreIntent) -> None:
        assert CHAT_STRUCTURE_RULES in _explore_dialogue(intent)

    @pytest.mark.parametrize("intent", ["question", "material"])
    def test_answers_may_use_a_diagram(self, intent: ExploreIntent) -> None:
        prompt = _explore_dialogue(intent)
        assert DIAGRAM_RULE in prompt
        assert NO_DIAGRAM_RULE not in prompt

    @pytest.mark.parametrize(
        ("intent", "wrap_up", "end_offered"),
        [("understood", False, False), ("question", True, False), ("end_session", False, True)],
    )
    def test_turns_that_explain_nothing_new_forbid_diagrams(
        self, intent: ExploreIntent, wrap_up: bool, end_offered: bool
    ) -> None:
        prompt = _explore_dialogue(intent, wrap_up=wrap_up, end_offered=end_offered)
        assert NO_DIAGRAM_RULE in prompt
        assert DIAGRAM_RULE not in prompt

    def test_an_unoffered_end_is_answered_like_a_question(self) -> None:
        assert DIAGRAM_RULE in _explore_dialogue("end_session", end_offered=False)
