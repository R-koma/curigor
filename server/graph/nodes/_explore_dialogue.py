from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from graph.explore import all_core_explained, known_aspect_id, merge_terms, next_aspect_id, overview_aspects
from graph.llm import llm
from graph.multimodal import load_image_blocks
from graph.nodes._explore_llm import analyze_explore_turn
from graph.nodes._shared import recent_messages_block
from graph.output_schemas import ExploreIntent, ExploreTermDraft
from graph.prompts.explore import EXPLORE_PROMPT_FINGERPRINT, build_explore_dialogue_prompt
from graph.session_end import end_confirmation_after
from graph.state import DepthMapState, EndConfirmationStatus, ExploreQuestion, ExploreTurnRecord, LearningState
from storage import get_storage

_EXPLAINING_INTENTS: frozenset[ExploreIntent] = frozenset({"next", "choose_aspect"})


@dataclass(frozen=True)
class ExploreTurnPlan:
    user_intent: ExploreIntent
    aspect_id: str | None
    explained_aspects: list[str]
    terms: list[ExploreTermDraft]
    question_summary: str
    wrap_up: bool
    end_confirmation: EndConfirmationStatus | None


def _target_aspect(
    intent: ExploreIntent, reference: str, depth_map: DepthMapState, explained: list[str]
) -> str | None:
    if intent == "end_session":
        return None
    if intent == "next":
        return next_aspect_id(depth_map, explained)
    known = known_aspect_id(reference, depth_map)
    if intent == "choose_aspect":
        return known or next_aspect_id(depth_map, explained)
    return known


async def prepare_explore_turn(state: LearningState) -> ExploreTurnPlan:
    depth_map = state["depth_map"]
    explained = list(state.get("explained_aspects") or [])
    analysis = await analyze_explore_turn(state)
    intent: ExploreIntent = analysis.user_intent if analysis else "question"
    aspect_id = _target_aspect(intent, analysis.aspect_id if analysis else "", depth_map, explained)
    if intent in _EXPLAINING_INTENTS and aspect_id is not None and aspect_id not in explained:
        explained.append(aspect_id)
    wrap_up = intent != "end_session" and not state.get("wrap_up_offered") and all_core_explained(depth_map, explained)
    return ExploreTurnPlan(
        user_intent=intent,
        aspect_id=aspect_id,
        explained_aspects=explained,
        terms=list(analysis.terms) if analysis else [],
        question_summary=analysis.question_summary.strip() if analysis and intent == "question" else "",
        wrap_up=wrap_up,
        end_confirmation=end_confirmation_after(
            state.get("end_confirmation"), wants_to_end=intent == "end_session", offer=wrap_up
        ),
    )


def _record(plan: ExploreTurnPlan) -> ExploreTurnRecord:
    return {"user_intent": plan.user_intent, "aspect_id": plan.aspect_id or "", "wrap_up": plan.wrap_up}


async def respond_explore(state: LearningState, plan: ExploreTurnPlan) -> dict[str, Any]:
    depth_map = state["depth_map"]
    questions: list[ExploreQuestion] = list(state.get("explore_questions") or [])
    updates: dict[str, Any] = {
        "turn_count": state["turn_count"] + 1,
        "should_generate_note": False,
        "explained_aspects": plan.explained_aspects,
        "explore_terms": merge_terms(state.get("explore_terms") or [], plan.terms),
        "explore_questions": questions,
        "explore_turn": _record(plan),
        "wrap_up_offered": bool(state.get("wrap_up_offered")) or plan.wrap_up,
        "end_confirmation": plan.end_confirmation,
    }
    if plan.end_confirmation == "confirmed":
        return updates

    target = next((a for a in depth_map["aspects"] if a["id"] == plan.aspect_id), None)
    prompt = build_explore_dialogue_prompt(
        topic=state["topic"],
        source=state.get("learning_source") or "",
        overview=overview_aspects(depth_map, state.get("explore_overview") or {}, plan.explained_aspects),
        target=target,
        intent=plan.user_intent,
        wrap_up=plan.wrap_up,
        end_offered=plan.end_confirmation == "offered",
        recent_messages=recent_messages_block(state, limit=8),
    )
    llm_messages: list[BaseMessage] = [SystemMessage(content=prompt)]
    image_blocks = await load_image_blocks(state["messages"][-1], get_storage())
    if image_blocks:
        llm_messages.append(HumanMessage(content=image_blocks))

    response = await llm.ainvoke(
        llm_messages,
        config={
            "metadata": {
                "prompt_fingerprint": EXPLORE_PROMPT_FINGERPRINT,
                "intent": plan.user_intent,
                "aspect_id": plan.aspect_id,
                "wrap_up": plan.wrap_up,
            }
        },
        task="explore-dialogue",
    )
    if response.id is None:
        response.id = str(uuid4())
    if plan.question_summary:
        updates["explore_questions"] = [
            *questions,
            {"question": plan.question_summary, "answer_message_id": response.id},
        ]
    return {**updates, "messages": [response]}
