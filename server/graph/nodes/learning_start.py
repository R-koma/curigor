from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from graph.intake_card import build_intake_card, draft_intake_card, intake_lead
from graph.memo_handoff import memo_kickoff
from graph.nodes._depth_map_generation import generate_depth_map
from graph.state import LearningState
from graph.trial import TRIAL_CORE_ASPECTS, TRIAL_PURPOSE, limit_core_aspects, trial_kickoff
from services.related_notes import find_related_notes


async def learning_start(state: LearningState) -> dict[str, Any]:
    """学習フローの開始: 最初の発言からトピックを正規化し、聞き取りカードを返す。

    API から learning_goal（目的）が渡っていれば、カードから目的の質問を除く。
    お試し（`trial`）は聞き取りを飛ばして地図駆動の対話から始める。地図の生成に失敗したら通常の聞き取りに戻す。
    """
    if state.get("memo_depth_map"):
        return await _start_from_memo(state)

    if state.get("trial"):
        started = await _start_trial(state)
        if started is not None:
            return started

    utterance = state["topic"]
    draft = await draft_intake_card(utterance)
    topic, card = build_intake_card(utterance, draft, ask_purpose=not state.get("learning_goal"))
    ask_topic = any(q.key == "topic" for q in card.questions)

    return {
        "messages": [
            HumanMessage(content=utterance),
            AIMessage(
                content=intake_lead(topic, ask_topic=ask_topic), additional_kwargs={"intake_card": card.model_dump()}
            ),
        ],
        "topic": topic,
        "turn_count": 1,
        "should_generate_note": False,
        "intake_complete": False,
        "intake_turns": 0,
    }


async def _start_from_memo(state: LearningState) -> dict[str, Any]:
    topic = state["topic"]
    depth_map = state["memo_depth_map"]
    related_notes = await find_related_notes(user_id=state["user_id"], topic=topic, purpose="")
    return {
        "messages": [
            HumanMessage(content=topic),
            AIMessage(content=memo_kickoff(topic, depth_map), additional_kwargs={"memo_kickoff": True}),
        ],
        "topic": topic,
        "turn_count": 1,
        "should_generate_note": False,
        "intake_complete": True,
        "intake_turns": 0,
        "learning_goal": "",
        "learning_source": state.get("learning_source") or "",
        "prior_knowledge": "",
        "related_notes": related_notes,
        "depth_map": depth_map,
        "map_covered": [],
        "intake_message_count": 1,
        "turn_analysis": None,
        "wrap_up_offered": False,
    }


async def _start_trial(state: LearningState) -> dict[str, Any] | None:
    topic = state["topic"]
    depth_map = await generate_depth_map(topic=topic, purpose=TRIAL_PURPOSE, source="", prior_knowledge="")
    if depth_map is None:
        return None
    return {
        "messages": [
            HumanMessage(content=topic),
            AIMessage(content=trial_kickoff(topic), additional_kwargs={"trial_kickoff": True}),
        ],
        "topic": topic,
        "turn_count": 1,
        "should_generate_note": False,
        "intake_complete": True,
        "intake_turns": 0,
        "learning_goal": TRIAL_PURPOSE,
        "learning_source": "",
        "prior_knowledge": "",
        "related_notes": [],
        "depth_map": limit_core_aspects(depth_map, TRIAL_CORE_ASPECTS),
        "map_covered": [],
        "intake_message_count": 1,
        "turn_analysis": None,
        "wrap_up_offered": False,
    }


__all__ = ["learning_start"]
