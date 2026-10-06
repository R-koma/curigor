from graph.topic_correction import topic_correction_card, topic_correction_text


def test_text_names_both_topics_and_the_consequences() -> None:
    text = topic_correction_text("この仕組み", "Linuxの仕組み")

    assert "「この仕組み」から「Linuxの仕組み」" in text
    assert "観点の地図を作り直し" in text
    assert "到達度は空になります" in text
    assert "対話の履歴は残ります" in text


def test_card_carries_both_topics() -> None:
    assert topic_correction_card("A", "B") == {"previous_topic": "A", "new_topic": "B"}
