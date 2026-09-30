from unittest.mock import AsyncMock, MagicMock, patch

from graph.intake_card import (
    FALLBACK_PURPOSE_OPTIONS,
    FALLBACK_SOURCE_OPTIONS,
    MAX_DESCRIPTION_LENGTH,
    MAX_LABEL_LENGTH,
    MAX_TOPIC_LENGTH,
    PRIOR_KNOWLEDGE_OPTIONS,
    build_intake_card,
    draft_intake_card,
    intake_lead,
)
from graph.llm import INTERNAL_LLM_TAG
from graph.output_schemas import IntakeCardDraft, IntakeOptionDraft
from schemas.intake_card import IntakeCard, IntakeQuestion


def _draft(**overrides: object) -> IntakeCardDraft:
    base: dict[str, object] = {
        "topic": "React Hooks",
        "purpose_options": [
            IntakeOptionDraft(label="仕事で使う"),
            IntakeOptionDraft(label="基礎を理解したい"),
            IntakeOptionDraft(label="面接対策"),
        ],
        "source_options": [
            IntakeOptionDraft(label="公式ドキュメント"),
            IntakeOptionDraft(label="書籍"),
            IntakeOptionDraft(label="動画講座"),
        ],
        "inferred_purpose": "",
    }
    base.update(overrides)
    return IntakeCardDraft.model_validate(base)


def _question(card: IntakeCard, key: str) -> IntakeQuestion:
    return next(q for q in card.questions if q.key == key)


class TestBuildIntakeCard:
    def test_uses_normalized_topic_and_draft_options(self) -> None:
        topic, card = build_intake_card("仕事でReactのフックを使うので学びたい", _draft(), ask_purpose=True)

        assert topic == "React Hooks"
        assert [q.key for q in card.questions] == ["purpose", "source", "prior_knowledge"]
        assert [o.label for o in _question(card, "purpose").options] == ["仕事で使う", "基礎を理解したい", "面接対策"]
        assert _question(card, "source").multi_select is True
        assert _question(card, "purpose").multi_select is False

    def test_prior_knowledge_options_are_fixed(self) -> None:
        _, card = build_intake_card("x", _draft(), ask_purpose=True)

        assert _question(card, "prior_knowledge").options == PRIOR_KNOWLEDGE_OPTIONS

    def test_falls_back_to_generic_card_when_draft_is_missing(self) -> None:
        topic, card = build_intake_card("  システムコール  ", None, ask_purpose=True)

        assert topic == "システムコール"
        assert _question(card, "purpose").options == FALLBACK_PURPOSE_OPTIONS
        assert _question(card, "source").options == FALLBACK_SOURCE_OPTIONS

    def test_blank_topic_in_draft_falls_back_to_utterance(self) -> None:
        topic, _ = build_intake_card("システムコール", _draft(topic="  "), ask_purpose=True)

        assert topic == "システムコール"

    def test_too_few_usable_options_fall_back_per_question(self) -> None:
        draft = _draft(source_options=[IntakeOptionDraft(label="書籍"), IntakeOptionDraft(label=" ")])

        _, card = build_intake_card("x", draft, ask_purpose=True)

        assert _question(card, "source").options == FALLBACK_SOURCE_OPTIONS
        assert len(_question(card, "purpose").options) == 3

    def test_options_are_deduplicated_and_capped_at_four(self) -> None:
        labels = ["A", "A", "B", "C", "D", "E"]
        draft = _draft(purpose_options=[IntakeOptionDraft(label=label) for label in labels])

        _, card = build_intake_card("x", draft, ask_purpose=True)

        assert [o.label for o in _question(card, "purpose").options] == ["A", "B", "C", "D"]

    def test_inferred_purpose_is_preselected_only_when_it_is_an_option(self) -> None:
        _, card = build_intake_card("x", _draft(inferred_purpose="仕事で使う"), ask_purpose=True)
        _, unknown = build_intake_card("x", _draft(inferred_purpose="存在しない"), ask_purpose=True)

        assert _question(card, "purpose").preselected == ["仕事で使う"]
        assert _question(unknown, "purpose").preselected == []

    def test_purpose_question_is_omitted_when_goal_is_already_known(self) -> None:
        _, card = build_intake_card("x", _draft(), ask_purpose=False)

        assert [q.key for q in card.questions] == ["source", "prior_knowledge"]


class TestLengthCaps:
    def test_long_labels_and_descriptions_are_truncated(self) -> None:
        draft = _draft(
            purpose_options=[
                IntakeOptionDraft(label="あ" * 300, description="い" * 300),
                IntakeOptionDraft(label="短い"),
            ]
        )

        _, card = build_intake_card("x", draft, ask_purpose=True)

        first = _question(card, "purpose").options[0]
        assert len(first.label) == MAX_LABEL_LENGTH
        assert len(first.description) == MAX_DESCRIPTION_LENGTH

    def test_labels_that_collide_after_truncation_are_deduplicated(self) -> None:
        long = "あ" * (MAX_LABEL_LENGTH + 10)
        draft = _draft(
            purpose_options=[
                IntakeOptionDraft(label=long + "1"),
                IntakeOptionDraft(label=long + "2"),
                IntakeOptionDraft(label="別の目的"),
            ]
        )

        _, card = build_intake_card("x", draft, ask_purpose=True)

        assert [o.label for o in _question(card, "purpose").options] == ["あ" * MAX_LABEL_LENGTH, "別の目的"]

    def test_llm_topic_is_truncated(self) -> None:
        topic, _ = build_intake_card("x", _draft(topic="あ" * 200), ask_purpose=True)

        assert len(topic) == MAX_TOPIC_LENGTH

    def test_fallback_topic_from_a_pasted_paragraph_is_truncated(self) -> None:
        topic, _ = build_intake_card("あ" * 500, None, ask_purpose=True)

        assert len(topic) == MAX_TOPIC_LENGTH


def test_lead_names_the_topic_and_allows_skipping() -> None:
    lead = intake_lead("React Hooks")

    assert "React Hooks" in lead
    assert "スキップ" in lead


class TestDraftIntakeCard:
    async def test_returns_structured_draft_with_internal_tag(self) -> None:
        mock_structured = MagicMock()
        with_config = mock_structured.with_structured_output.return_value.with_config
        with_config.return_value = MagicMock(ainvoke=AsyncMock(return_value=_draft()))
        with patch("graph.intake_card.llm_structured", mock_structured):
            result = await draft_intake_card("Reactのフック")

        assert result == _draft()
        with_config.assert_called_once_with(tags=[INTERNAL_LLM_TAG])

    async def test_tags_the_call_with_the_intake_prompt_fingerprint(self) -> None:
        from graph.prompts.intake import INTAKE_PROMPT_FINGERPRINT

        mock_structured = MagicMock()
        runnable = MagicMock(ainvoke=AsyncMock(return_value=_draft()))
        mock_structured.with_structured_output.return_value.with_config.return_value = runnable
        with patch("graph.intake_card.llm_structured", mock_structured):
            await draft_intake_card("Reactのフック")

        config = runnable.ainvoke.call_args.kwargs["config"]
        assert config["metadata"]["prompt_fingerprint"] == INTAKE_PROMPT_FINGERPRINT

    async def test_returns_none_on_llm_error(self) -> None:
        mock_structured = MagicMock()
        mock_structured.with_structured_output.return_value.with_config.return_value = MagicMock(
            ainvoke=AsyncMock(side_effect=RuntimeError("boom"))
        )
        with patch("graph.intake_card.llm_structured", mock_structured):
            assert await draft_intake_card("x") is None

    async def test_returns_none_on_unexpected_type(self) -> None:
        mock_structured = MagicMock()
        mock_structured.with_structured_output.return_value.with_config.return_value = MagicMock(
            ainvoke=AsyncMock(return_value={"topic": "x"})
        )
        with patch("graph.intake_card.llm_structured", mock_structured):
            assert await draft_intake_card("x") is None
