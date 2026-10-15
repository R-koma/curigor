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

    def test_states_each_rule(self) -> None:
        assert "```言語名" in FORMATTING_RULES
        assert "$…$" in FORMATTING_RULES
        assert "$$…$$" in FORMATTING_RULES
        assert "\\$5" in FORMATTING_RULES
        assert "```mermaid" in DIAGRAM_RULE
