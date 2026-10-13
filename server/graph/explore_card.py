from graph.explore import NO_MATERIAL_LABEL
from graph.intake_card import MAX_OPTIONS, MAX_TOPIC_LENGTH, source_options, topic_question
from graph.output_schemas import IntakeCardDraft
from schemas.intake_card import IntakeCard, IntakeOption, IntakeQuestion


def build_explore_card(utterance: str, draft: IntakeCardDraft | None) -> tuple[str, IntakeCard]:
    topic = ((draft.topic.strip() if draft else "") or utterance.strip())[:MAX_TOPIC_LENGTH]
    questions: list[IntakeQuestion] = []
    if draft is not None and not draft.topic_is_clear:
        questions.append(topic_question(draft))
    options = [
        *source_options(draft)[: MAX_OPTIONS - 1],
        IntakeOption(label=NO_MATERIAL_LABEL, description="AI に一から教わる"),
    ]
    questions.append(
        IntakeQuestion(
            key="source",
            header="教材",
            question="手元に教材はありますか？（複数選択可）",
            options=options,
            multi_select=True,
        )
    )
    return topic, IntakeCard(questions=questions)


def explore_lead(topic: str, *, ask_topic: bool) -> str:
    if ask_topic:
        return "学びたい内容を、もう少し具体的に教えてください。あわせて、手元の教材を教えてください。"
    return (
        f"{topic}を一から学ぶんですね。始める前に、手元の教材を教えてください。"
        f"無ければ「{NO_MATERIAL_LABEL}」で大丈夫です。"
    )
