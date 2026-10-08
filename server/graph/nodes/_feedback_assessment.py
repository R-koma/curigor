from collections.abc import Sequence
from typing import Any

from langchain_core.messages import BaseMessage, SystemMessage

from graph.llm import llm_structured
from graph.output_schemas import DialogueAnalysis, FeedbackOutput
from graph.prompts import ANALYZE_RESPONSE_PROMPT, GENERATE_FEEDBACK_PROMPT
from graph.prompts.feedback import build_aspect_section


def format_conversation_history(messages: Sequence[BaseMessage]) -> str:
    return "\n".join(f"{'ユーザー' if msg.type == 'human' else 'AI'}: {msg.content}" for msg in messages)


def format_note_text(topic: str, content: str) -> str:
    return f"トピック: {topic}\n\n{content}"


async def analyze_dialogue(topic: str, conversation_history: str) -> DialogueAnalysis:
    prompt = ANALYZE_RESPONSE_PROMPT.format(topic=topic, conversation_history=conversation_history)
    analysis_llm = llm_structured.with_structured_output(DialogueAnalysis, task="analyze-dialogue")
    result = await analysis_llm.ainvoke([SystemMessage(content=prompt)], config={"run_name": "analyze-dialogue"})
    if not isinstance(result, DialogueAnalysis):
        raise RuntimeError("LLM did not return structured DialogueAnalysis")
    return result


async def score_feedback(
    topic: str, analysis: DialogueAnalysis, aspect_map: dict[str, Any] | None, note_text: str
) -> FeedbackOutput:
    prompt = GENERATE_FEEDBACK_PROMPT.format(
        topic=topic, analysis=analysis.to_markdown(), aspect_section=build_aspect_section(aspect_map)
    )
    scoring_llm = llm_structured.with_structured_output(FeedbackOutput, task="generate-feedback-scores")
    result = await scoring_llm.ainvoke(
        [SystemMessage(content=prompt), {"role": "user", "content": note_text}],
        config={"run_name": "generate-feedback-scores"},
    )
    if not isinstance(result, FeedbackOutput):
        raise RuntimeError("LLM did not return structured FeedbackOutput")
    return result
