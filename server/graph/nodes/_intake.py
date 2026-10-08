"""聞き取りの回答（目的・出典・前提知識）から深さの地図を作り、学習を始める。intake_complete=False のターンで呼ばれる。

完了ターンで地図生成が失敗した場合、`messages` を含まない dict を返す。
その場合は呼び出し元（learning_dialogue のルーター）が legacy 経路で応答を生成する
（このモジュールから legacy の prepare_turn/respond を呼ぶと learning_dialogue.py との
circular import になるため、responsibility を呼び出し元へ返す）。
"""

from typing import Any, NamedTuple

from langchain_core.messages import SystemMessage

from graph.intake_card import MAX_TOPIC_LENGTH
from graph.llm import llm
from graph.nodes._depth_map_generation import generate_depth_map
from graph.nodes._intake_analysis import extract_intake
from graph.nodes._shared import recent_messages_block
from graph.prompts.intake import INTAKE_PROMPT_FINGERPRINT, build_learning_kickoff_prompt
from graph.state import LearningState
from graph.trial import TRIAL_CORE_ASPECTS, limit_core_aspects
from services.related_notes import find_related_notes


def _merge_field(existing: str | None, extracted: str) -> str:
    return extracted or (existing or "")


def _card_answers(state: LearningState) -> dict[str, Any] | None:
    last = state["messages"][-1] if state["messages"] else None
    if last is None or last.type != "human":
        return None
    answers = last.additional_kwargs.get("intake_answers")
    return answers if isinstance(answers, dict) else None


class IntakeFields(NamedTuple):
    topic: str
    purpose: str
    source: str
    prior_knowledge: str


def _topic_was_asked(state: LearningState) -> bool:
    messages = state["messages"]
    if len(messages) < 2:
        return False
    card = messages[-2].additional_kwargs.get("intake_card")
    return isinstance(card, dict) and any(q.get("key") == "topic" for q in card.get("questions") or [])


def _confirmed_topic(current: str, candidate: str) -> str:
    return candidate.strip()[:MAX_TOPIC_LENGTH] or current


async def _collect_intake_fields(state: LearningState, recent_messages: str) -> IntakeFields:
    answers = _card_answers(state)
    if answers is not None:
        return IntakeFields(
            _confirmed_topic(state["topic"], str(answers.get("topic") or "")),
            str(answers.get("purpose") or "") or (state.get("learning_goal") or ""),
            "、".join(str(s) for s in answers.get("source") or []),
            str(answers.get("prior_knowledge") or ""),
        )
    confirm_topic = _topic_was_asked(state)
    extraction = await extract_intake(state, recent_messages=recent_messages, confirm_topic=confirm_topic)
    return IntakeFields(
        _confirmed_topic(state["topic"], extraction.topic if extraction and confirm_topic else ""),
        _merge_field(state.get("learning_goal"), extraction.purpose if extraction else ""),
        _merge_field(state.get("learning_source"), extraction.source if extraction else ""),
        _merge_field(state.get("prior_knowledge"), extraction.prior_knowledge if extraction else ""),
    )


async def handle_intake_turn(state: LearningState) -> dict[str, Any]:
    recent_messages = recent_messages_block(state)
    topic, purpose, source, prior_knowledge = await _collect_intake_fields(state, recent_messages)
    related_notes = await find_related_notes(user_id=state["user_id"], topic=topic, purpose=purpose)

    base_updates: dict[str, Any] = {
        "intake_complete": True,
        "topic": topic,
        "intake_turns": state.get("intake_turns", 0) + 1,
        "learning_goal": purpose,
        "learning_source": source,
        "prior_knowledge": prior_knowledge,
        "turn_count": state["turn_count"] + 1,
        "should_generate_note": False,
        "related_notes": related_notes,
    }

    depth_map = await generate_depth_map(
        topic=topic, purpose=purpose, source=source, prior_knowledge=prior_knowledge, related_notes=related_notes
    )
    if depth_map is None:
        return base_updates
    if state.get("trial"):
        depth_map = limit_core_aspects(depth_map, TRIAL_CORE_ASPECTS)

    kickoff_prompt = build_learning_kickoff_prompt(
        topic=topic,
        purpose=purpose,
        source=source,
        prior_knowledge=prior_knowledge,
        recent_messages=recent_messages,
    )
    response = await llm.ainvoke(
        [SystemMessage(content=kickoff_prompt)],
        config={"metadata": {"prompt_fingerprint": INTAKE_PROMPT_FINGERPRINT}},
    )
    return {
        **base_updates,
        "messages": [response],
        "depth_map": depth_map,
        "map_covered": [],
        "intake_message_count": len(state["messages"]),
        "turn_analysis": None,
        "wrap_up_offered": False,
    }
