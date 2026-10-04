from typing import Any

from langgraph.graph import END, StateGraph

from graph.nodes.generate_feedback import generate_feedback
from graph.nodes.generate_note import generate_note
from graph.nodes.learning_dialogue import learning_dialogue
from graph.nodes.learning_start import learning_start
from graph.nodes.review_dialogue import review_dialogue
from graph.nodes.review_start import review_start
from graph.nodes.synthesis import finish_synthesis, synthesis_dialogue, synthesis_start
from graph.nodes.update_note_and_feedback import update_note_and_feedback
from graph.state import LearningState


def route_entry(state: LearningState) -> str:
    if state.get("session_type") == "review":
        return "review_start"
    if state.get("session_type") == "synthesis":
        return "synthesis_start"
    return "learning_start"


def route_after_synthesis_dialogue(state: LearningState) -> str:
    if not state["should_generate_note"]:
        return "synthesis_dialogue"
    return "finish_synthesis"


def route_after_learning_dialogue(state: LearningState) -> str:
    if not state["should_generate_note"]:
        return "learning_dialogue"
    return "generate_note"


def route_after_review_dialogue(state: LearningState) -> str:
    if not state["should_generate_note"]:
        return "review_dialogue"
    return "update_note_and_feedback"


def build_learning_graph(checkpointer: Any) -> Any:
    """session_type で learning / review を入口から完全に別パスへ分岐させる。"""
    graph = StateGraph(LearningState)

    graph.add_node("learning_start", learning_start)
    graph.add_node("learning_dialogue", learning_dialogue)
    graph.add_node("review_start", review_start)
    graph.add_node("review_dialogue", review_dialogue)
    graph.add_node("generate_note", generate_note)
    graph.add_node("generate_feedback", generate_feedback)
    graph.add_node("update_note_and_feedback", update_note_and_feedback)
    graph.add_node("synthesis_start", synthesis_start)
    graph.add_node("synthesis_dialogue", synthesis_dialogue)
    graph.add_node("finish_synthesis", finish_synthesis)

    graph.set_conditional_entry_point(
        route_entry,
        {"learning_start": "learning_start", "review_start": "review_start", "synthesis_start": "synthesis_start"},
    )

    graph.add_edge("learning_start", "learning_dialogue")
    graph.add_conditional_edges(
        "learning_dialogue",
        route_after_learning_dialogue,
        {
            "generate_note": "generate_note",
            "learning_dialogue": "learning_dialogue",
        },
    )
    graph.add_edge("generate_note", "generate_feedback")
    graph.add_edge("generate_feedback", END)

    graph.add_edge("review_start", "review_dialogue")
    graph.add_conditional_edges(
        "review_dialogue",
        route_after_review_dialogue,
        {
            "update_note_and_feedback": "update_note_and_feedback",
            "review_dialogue": "review_dialogue",
        },
    )
    graph.add_edge("update_note_and_feedback", END)

    graph.add_edge("synthesis_start", "synthesis_dialogue")
    graph.add_conditional_edges(
        "synthesis_dialogue",
        route_after_synthesis_dialogue,
        {"finish_synthesis": "finish_synthesis", "synthesis_dialogue": "synthesis_dialogue"},
    )
    graph.add_edge("finish_synthesis", END)

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["learning_dialogue", "review_dialogue", "synthesis_dialogue"],
    )
