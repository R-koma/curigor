from graph.intake_summary import build_intake_summary


def test_carries_the_three_answers() -> None:
    summary = build_intake_summary(
        {"learning_goal": "基礎を身につける", "learning_source": "入門書", "prior_knowledge": "初めて学ぶ"}
    )
    assert summary is not None
    assert summary.model_dump() == {"purpose": "基礎を身につける", "source": "入門書", "prior_knowledge": "初めて学ぶ"}


def test_strips_whitespace_and_blanks_unanswered_fields() -> None:
    summary = build_intake_summary({"learning_source": " 入門書 ", "prior_knowledge": "  "})
    assert summary is not None
    assert summary.model_dump() == {"purpose": "", "source": "入門書", "prior_knowledge": ""}


def test_is_none_when_every_field_is_blank() -> None:
    assert build_intake_summary({"learning_goal": "", "learning_source": "  ", "prior_knowledge": None}) is None


def test_is_none_when_the_keys_are_missing() -> None:
    assert build_intake_summary({}) is None
