from graph.explore import NO_MATERIAL_LABEL
from graph.explore_card import build_explore_card, explore_lead
from graph.output_schemas import IntakeCardDraft, IntakeOptionDraft


def _draft(**overrides: object) -> IntakeCardDraft:
    values: dict[str, object] = {
        "topic": "二分探索",
        "purpose_options": [IntakeOptionDraft(label="基礎"), IntakeOptionDraft(label="実務")],
        "source_options": [
            IntakeOptionDraft(label="入門書"),
            IntakeOptionDraft(label="動画講座"),
            IntakeOptionDraft(label="公式ドキュメント"),
            IntakeOptionDraft(label="授業"),
        ],
    }
    values.update(overrides)
    return IntakeCardDraft(**values)  # type: ignore[arg-type]


def test_asks_only_the_material_with_a_no_material_option() -> None:
    topic, card = build_explore_card("二分探索を学びたい", _draft())

    assert topic == "二分探索"
    assert [q.key for q in card.questions] == ["source"]
    labels = [o.label for o in card.questions[0].options]
    assert labels[-1] == NO_MATERIAL_LABEL
    assert len(labels) <= 4
    assert card.questions[0].multi_select is True


def test_asks_the_topic_first_when_the_utterance_is_vague() -> None:
    _, card = build_explore_card("これを学びたい", _draft(topic_is_clear=False, topic_candidates=["二分探索"]))

    assert [q.key for q in card.questions] == ["topic", "source"]


def test_falls_back_to_the_utterance_without_a_draft() -> None:
    topic, card = build_explore_card("二分探索", None)

    assert topic == "二分探索"
    assert [q.key for q in card.questions] == ["source"]


def test_lead_mentions_the_topic_unless_it_is_asked() -> None:
    assert "二分探索" in explore_lead("二分探索", ask_topic=False)
    assert "二分探索" not in explore_lead("二分探索", ask_topic=True)
