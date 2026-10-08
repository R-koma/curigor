from graph.topic_correction import same_topic, topic_correction_card, topic_correction_text, topic_edit_text


def test_text_names_both_topics_and_the_consequences() -> None:
    text = topic_correction_text("この仕組み", "Linuxの仕組み")

    assert "「この仕組み」から「Linuxの仕組み」" in text
    assert "観点の地図を作り直し" in text
    assert "到達度は空になります" in text
    assert "対話の履歴は残ります" in text


def test_card_carries_both_topics() -> None:
    assert topic_correction_card("A", "B") == {"previous_topic": "A", "new_topic": "B"}


def test_same_topic_ignores_width_case_and_surrounding_spaces() -> None:
    assert same_topic(" ＴＣＰ ", "tcp")
    assert not same_topic("TCP", "UDP")


def test_topic_edit_text_names_the_new_topic() -> None:
    assert topic_edit_text("Linuxの仕組み") == "トピックを「Linuxの仕組み」に変更しました"
