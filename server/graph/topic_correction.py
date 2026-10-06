def topic_correction_text(previous_topic: str, new_topic: str) -> str:
    return (
        f"学習トピックを「{previous_topic}」から「{new_topic}」に変更しますか？\n\n"
        "変更すると、観点の地図を作り直し、これまでの到達度は空になります。対話の履歴は残ります。"
    )


def topic_correction_card(previous_topic: str, new_topic: str) -> dict[str, str]:
    return {"previous_topic": previous_topic, "new_topic": new_topic}
