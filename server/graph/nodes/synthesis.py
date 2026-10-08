from collections.abc import Sequence
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from core.database import get_pool
from graph.llm import llm, llm_structured
from graph.output_schemas import SynthesisInsightsOutput
from graph.prompts.synthesis import (
    SYNTHESIS_PROMPT_FINGERPRINT,
    build_synthesis_dialogue_prompt,
    build_synthesis_insights_prompt,
    build_synthesis_opening_prompt,
)
from graph.state import LearningState
from repositories import synthesis_insight_repository

_PROMPT_CONFIG: RunnableConfig = {"metadata": {"prompt_fingerprint": SYNTHESIS_PROMPT_FINGERPRINT}}


def current_connection_index(messages: Sequence[BaseMessage]) -> int:
    return sum(1 for m in messages if m.type == "human") - 2


async def synthesis_start(state: LearningState) -> dict[str, Any]:
    connections = state.get("synthesis_connections") or []
    prompt = build_synthesis_opening_prompt(
        collection_name=state["topic"], total=len(connections), first=connections[0]
    )
    response = await llm.ainvoke([SystemMessage(content=prompt)], config=_PROMPT_CONFIG, task="synthesis-start")
    return {
        "messages": [HumanMessage(content=state["topic"]), response],
        "turn_count": 1,
        "should_generate_note": False,
    }


async def synthesis_dialogue(state: LearningState) -> dict[str, Any]:
    connections = state.get("synthesis_connections") or []
    index = current_connection_index(state["messages"])
    current = connections[index] if 0 <= index < len(connections) else None
    next_connection = connections[index + 1] if 0 <= index + 1 < len(connections) else None
    prompt = build_synthesis_dialogue_prompt(
        collection_name=state["topic"],
        notes=state.get("synthesis_notes", ""),
        total=len(connections),
        current=current,
        next_connection=next_connection,
    )
    response = await llm.ainvoke(
        [SystemMessage(content=prompt), *state["messages"]], config=_PROMPT_CONFIG, task="synthesis-dialogue"
    )
    return {
        "messages": [response],
        "turn_count": state["turn_count"] + 1,
        "should_generate_note": False,
    }


async def finish_synthesis(state: LearningState) -> dict[str, Any]:
    connections = state.get("synthesis_connections") or []
    conversation = "\n".join(f"{'学習者' if m.type == 'human' else 'AI'}: {m.content}" for m in state["messages"][1:])
    prompt = build_synthesis_insights_prompt(connections=connections, conversation=conversation)
    result: Any = await llm_structured.with_structured_output(
        SynthesisInsightsOutput, task="synthesis-insights"
    ).ainvoke([SystemMessage(content=prompt)], config=_PROMPT_CONFIG)
    if not isinstance(result, SynthesisInsightsOutput):
        raise RuntimeError("LLM did not return structured SynthesisInsightsOutput output")

    titles = {c["id"]: c["title"] for c in connections}
    insights = [
        (titles[i.connection_id], i.content.strip())
        for i in result.insights
        if i.connection_id in titles and i.content.strip()
    ]
    if insights:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await synthesis_insight_repository.insert_many(
                conn,
                collection_id=state["collection_id"],
                dialogue_session_id=state["dialogue_session_id"],
                insights=insights,
            )
    return {}


__all__ = ["current_connection_index", "finish_synthesis", "synthesis_dialogue", "synthesis_start"]
