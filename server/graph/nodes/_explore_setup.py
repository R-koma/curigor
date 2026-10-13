from typing import Any, NamedTuple

from langchain_core.messages import AIMessage

from graph.explore import EXPLORE_PRIOR_KNOWLEDGE, NO_MATERIAL_LABEL, overview_aspects, overview_text
from graph.intake_card import MAX_TOPIC_LENGTH
from graph.nodes._depth_map_generation import generate_depth_map
from graph.nodes._explore_llm import draft_overview
from graph.state import LearningState
from schemas.intake_card import MAX_ANSWER_LENGTH

SETUP_FAILED_TEXT = "全体像をうまく作れませんでした。学びたいトピックを、もう一度短く送ってください。"


class _SetupFields(NamedTuple):
    topic: str
    source: str


def _setup_fields(state: LearningState) -> _SetupFields:
    last = state["messages"][-1]
    current_topic = state["topic"]
    answers = last.additional_kwargs.get("intake_answers")
    if isinstance(answers, dict):
        topic = str(answers.get("topic") or "").strip()[:MAX_TOPIC_LENGTH] or current_topic
        sources = [str(s) for s in answers.get("source") or [] if str(s) != NO_MATERIAL_LABEL]
        return _SetupFields(topic, "、".join(sources))
    text = str(last.content).strip()
    if state.get("explore_setup_failed"):
        return _SetupFields(text[:MAX_TOPIC_LENGTH] or current_topic, state.get("learning_source") or "")
    return _SetupFields(current_topic, "" if text == NO_MATERIAL_LABEL else text[:MAX_ANSWER_LENGTH])


async def handle_explore_setup_turn(state: LearningState) -> dict[str, Any]:
    topic, source = _setup_fields(state)
    base: dict[str, Any] = {
        "topic": topic,
        "learning_source": source,
        "turn_count": state["turn_count"] + 1,
        "should_generate_note": False,
        "explore_turn": None,
        "end_confirmation": None,
    }
    depth_map = await generate_depth_map(
        topic=topic, purpose="", source=source, prior_knowledge=EXPLORE_PRIOR_KNOWLEDGE
    )
    if depth_map is None:
        return {
            **base,
            "explore_setup_failed": True,
            "messages": [AIMessage(content=SETUP_FAILED_TEXT, additional_kwargs={"explore_setup_failed": True})],
        }
    summaries = await draft_overview(topic, depth_map)
    text = overview_text(topic, overview_aspects(depth_map, summaries, []))
    return {
        **base,
        "explore_setup_failed": False,
        "depth_map": depth_map,
        "explore_overview": summaries,
        "messages": [AIMessage(content=text, additional_kwargs={"explore_overview": True})],
    }
