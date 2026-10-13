import operator
from typing import Annotated, Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph
from typing_extensions import TypedDict


class _State(TypedDict):
    session_type: str
    log: Annotated[list[str], operator.add]


def _node(name: str) -> Any:
    async def run(state: _State) -> dict[str, Any]:
        return {"log": [name]}

    return run


def _build(paths: list[str], saver: InMemorySaver) -> Any:
    graph = StateGraph(_State)
    for path in paths:
        graph.add_node(f"{path}_start", _node(f"{path}_start"))
        graph.add_node(f"{path}_dialogue", _node(f"{path}_dialogue"))
        graph.add_edge(f"{path}_start", f"{path}_dialogue")
        graph.add_edge(f"{path}_dialogue", f"{path}_dialogue")
    graph.set_conditional_entry_point(
        lambda s: f"{s['session_type']}_start", {f"{p}_start": f"{p}_start" for p in paths}
    )
    return graph.compile(checkpointer=saver, interrupt_before=[f"{p}_dialogue" for p in paths])


async def test_a_thread_started_before_a_new_entry_path_resumes_on_the_new_graph() -> None:
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "t1"}}
    old = _build(["learning", "review", "synthesis"], saver)
    await old.ainvoke({"session_type": "learning", "log": []}, config)

    new = _build(["learning", "review", "synthesis", "explore"], saver)
    await new.ainvoke(None, config)
    await new.ainvoke(None, config)

    state = await new.aget_state(config)
    assert state.values["log"] == ["learning_start", "learning_dialogue", "learning_dialogue"]
    assert state.next == ("learning_dialogue",)
