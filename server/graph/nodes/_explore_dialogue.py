from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from graph.explore import merge_terms
from graph.llm import llm
from graph.multimodal import load_image_blocks
from graph.nodes._explore_llm import analyze_explore_turn
from graph.nodes._shared import recent_messages_block
from graph.output_schemas import ExploreIntent, ExploreTermDraft
from graph.prompts.explore import EXPLORE_PROMPT_FINGERPRINT, build_explore_dialogue_prompt
from graph.session_end import end_confirmation_after
from graph.state import EndConfirmationStatus, ExploreQuestion, ExploreTurnRecord, LearningState
from storage import get_storage

_RECORDED_INTENTS: frozenset[ExploreIntent] = frozenset({"question", "material"})


@dataclass(frozen=True)
class ExploreTurnPlan:
    user_intent: ExploreIntent
    topic: str
    terms: list[ExploreTermDraft]
    question_summary: str
    wrap_up: bool
    end_confirmation: EndConfirmationStatus | None


async def prepare_explore_turn(state: LearningState) -> ExploreTurnPlan:
    analysis = await analyze_explore_turn(state)
    intent: ExploreIntent = analysis.user_intent if analysis else "question"
    wrap_up = intent == "understood" and bool(state.get("explore_questions")) and not state.get("wrap_up_offered")
    return ExploreTurnPlan(
        user_intent=intent,
        topic=analysis.topic.strip() if analysis else "",
        terms=list(analysis.terms) if analysis else [],
        question_summary=analysis.question_summary.strip() if analysis and intent in _RECORDED_INTENTS else "",
        wrap_up=wrap_up,
        end_confirmation=end_confirmation_after(
            state.get("end_confirmation"), wants_to_end=intent == "end_session", offer=wrap_up
        ),
    )


def _record(plan: ExploreTurnPlan) -> ExploreTurnRecord:
    return {"user_intent": plan.user_intent, "wrap_up": plan.wrap_up}


async def respond_explore(state: LearningState, plan: ExploreTurnPlan) -> dict[str, Any]:
    questions: list[ExploreQuestion] = list(state.get("explore_questions") or [])
    updates: dict[str, Any] = {
        "turn_count": state["turn_count"] + 1,
        "should_generate_note": False,
        "explore_terms": merge_terms(state.get("explore_terms") or [], plan.terms),
        "explore_questions": questions,
        "explore_turn": _record(plan),
        "wrap_up_offered": bool(state.get("wrap_up_offered")) or plan.wrap_up,
        "end_confirmation": plan.end_confirmation,
    }
    if plan.end_confirmation == "confirmed":
        return updates

    prompt = build_explore_dialogue_prompt(
        topic=state["topic"],
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
