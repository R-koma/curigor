import logging

from langchain_core.messages import SystemMessage

from graph.llm import INTERNAL_LLM_TAG, llm_structured
from graph.output_schemas import IntakeCardDraft, IntakeOptionDraft
from graph.prompts.intake import INTAKE_PROMPT_FINGERPRINT, build_intake_card_prompt
from schemas.intake_card import IntakeCard, IntakeOption, IntakeQuestion

logger = logging.getLogger(__name__)

MIN_OPTIONS = 2
MAX_OPTIONS = 4
MAX_LABEL_LENGTH = 40
MAX_DESCRIPTION_LENGTH = 60
MAX_TOPIC_LENGTH = 60
MAX_TOPIC_OPTIONS = 3

FALLBACK_PURPOSE_OPTIONS = [
    IntakeOption(label="基礎を理解したい", description="仕組みや用語を押さえたい"),
    IntakeOption(label="仕事・実務で使いたい"),
    IntakeOption(label="試験・資格の対策"),
    IntakeOption(label="興味・教養として"),
]
FALLBACK_SOURCE_OPTIONS = [
    IntakeOption(label="書籍"),
    IntakeOption(label="動画・オンライン講座"),
    IntakeOption(label="公式ドキュメント・Web記事"),
    IntakeOption(label="授業・研修"),
]
PRIOR_KNOWLEDGE_OPTIONS = [
    IntakeOption(label="初めて学ぶ", description="ほとんど知らない"),
    IntakeOption(label="聞いたことはある", description="言葉は知っているが説明はできない"),
    IntakeOption(label="ある程度説明できる", description="基本は自分の言葉で説明できる"),
    IntakeOption(label="使ったことがある", description="実務や演習で使った経験がある"),
]


async def draft_intake_card(utterance: str) -> IntakeCardDraft | None:
    runnable = llm_structured.with_structured_output(IntakeCardDraft, task="generate-intake-card").with_config(
        tags=[INTERNAL_LLM_TAG]
    )
    try:
        result = await runnable.ainvoke(
            [SystemMessage(content=build_intake_card_prompt(utterance=utterance))],
            config={"metadata": {"prompt_fingerprint": INTAKE_PROMPT_FINGERPRINT}},
        )
    except Exception:
        logger.warning("intake card generation failed", exc_info=True)
        return None
    if not isinstance(result, IntakeCardDraft):
        logger.warning("intake card generation returned unexpected type %s", type(result).__name__)
        return None
    return result


def _options(drafts: list[IntakeOptionDraft], fallback: list[IntakeOption]) -> list[IntakeOption]:
    seen: set[str] = set()
    options: list[IntakeOption] = []
    for draft in drafts:
        label = draft.label.strip()[:MAX_LABEL_LENGTH]
        if not label or label in seen:
            continue
        seen.add(label)
        options.append(IntakeOption(label=label, description=draft.description.strip()[:MAX_DESCRIPTION_LENGTH]))
    if len(options) < MIN_OPTIONS:
        return fallback
    return options[:MAX_OPTIONS]


def _topic_options(candidates: list[str]) -> list[IntakeOption]:
    labels = dict.fromkeys(c.strip()[:MAX_LABEL_LENGTH] for c in candidates)
    return [IntakeOption(label=label) for label in labels if label][:MAX_TOPIC_OPTIONS]


def build_intake_card(utterance: str, draft: IntakeCardDraft | None, *, ask_purpose: bool) -> tuple[str, IntakeCard]:
    topic = ((draft.topic.strip() if draft else "") or utterance.strip())[:MAX_TOPIC_LENGTH]
    purpose_options = _options(draft.purpose_options, FALLBACK_PURPOSE_OPTIONS) if draft else FALLBACK_PURPOSE_OPTIONS
    source_options = _options(draft.source_options, FALLBACK_SOURCE_OPTIONS) if draft else FALLBACK_SOURCE_OPTIONS
    inferred = draft.inferred_purpose.strip()[:MAX_LABEL_LENGTH] if draft else ""

    questions: list[IntakeQuestion] = []
    if draft is not None and not draft.topic_is_clear:
        questions.append(
            IntakeQuestion(
                key="topic",
                header="トピック",
                question="何について学びますか？",
                options=_topic_options(draft.topic_candidates),
            )
        )
    if ask_purpose:
        questions.append(
            IntakeQuestion(
                key="purpose",
                header="目的",
                question="今回、何ができるようになりたいですか？",
                options=purpose_options,
                preselected=[inferred] if inferred in {o.label for o in purpose_options} else [],
            )
        )
    questions.append(
        IntakeQuestion(
            key="source",
            header="教材",
            question="何を使って学びますか？（複数選択可）",
            options=source_options,
            multi_select=True,
        )
    )
    questions.append(
        IntakeQuestion(
            key="prior_knowledge",
            header="今の理解",
            question="このトピックについて、今どのくらい知っていますか？",
            options=PRIOR_KNOWLEDGE_OPTIONS,
        )
    )
    return topic, IntakeCard(questions=questions)


def intake_lead(topic: str, *, ask_topic: bool = False) -> str:
    if ask_topic:
        return "学びたい内容を、もう少し具体的に教えてください。答えにくいものはスキップして大丈夫です。"
    return f"{topic}を学ぶんですね。始める前に、少しだけ教えてください。答えにくいものはスキップして大丈夫です。"
