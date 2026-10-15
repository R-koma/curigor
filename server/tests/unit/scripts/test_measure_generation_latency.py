from typing import Any

from langchain_core.runnables import RunnableLambda

from scripts.measure_generation_latency import CallRecorder, _timed, compare, summarize


def _run(session_id: str, kind: str, total_s: float, calls: dict[str, float]) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "kind": kind,
        "messages": 12,
        "total_s": total_s,
        "calls": [{"name": name, "start_s": 0.0, "duration_s": d} for name, d in calls.items()],
    }


def _report(commit: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    return {"git": {"commit": commit, "dirty": False}, "runs_per_session": 3, "summary": summarize(runs)}


def test_summarize_takes_the_median_per_session_and_per_kind() -> None:
    runs = [
        _run("s-learning", "learning", 10.0, {"generate-note-content": 4.0}),
        _run("s-learning", "learning", 14.0, {"generate-note-content": 6.0}),
        _run("s-learning", "learning", 12.0, {"generate-note-content": 5.0}),
        _run("s-explore", "explore", 6.0, {"summarize-explore-answers": 2.0}),
    ]

    summary = summarize(runs)

    learning = summary["sessions"]["s-learning"]
    assert (learning["runs"], learning["median_s"], learning["min_s"], learning["max_s"]) == (3, 12.0, 10.0, 14.0)
    assert learning["calls_median_s"] == {"generate-note-content": 5.0}
    assert summary["kinds"]["learning"] == {"runs": 3, "median_s": 12.0, "max_s": 14.0}
    assert summary["kinds"]["explore"]["median_s"] == 6.0


def test_compare_shows_the_change_in_seconds_and_percent() -> None:
    before = _report("aaa1111", [_run("s1", "explore", 10.0, {"summarize-explore-answers": 3.0})])
    after = _report("bbb2222", [_run("s1", "explore", 7.5, {"summarize-explore-answers": 3.1})])

    table = compare(before, after)

    assert "`aaa1111` → `bbb2222`" in table
    assert "| explore（全体） | 10.00 s | 7.50 s | -2.50 s (-25.0%) |" in table
    assert "| `summarize-explore-answers` | 3.00 s | 3.10 s |" in table


def test_compare_skips_sessions_measured_only_once() -> None:
    before = _report("aaa1111", [_run("s1", "learning", 10.0, {"estimate-category": 1.0})])
    after = _report("bbb2222", [_run("s2", "learning", 8.0, {"estimate-category": 1.0})])

    table = compare(before, after)

    assert "`s1`" not in table
    assert "`s2`" not in table
    assert "| learning（全体） | 10.00 s | 8.00 s |" in table


async def test_recorder_times_calls_through_bound_runnables() -> None:
    async def answer(value: int) -> int:
        return value

    async def node(state: dict[str, Any]) -> dict[str, Any]:
        bound = RunnableLambda(answer).with_config(tags=["internal"])
        await bound.ainvoke(1, config={"run_name": "generate-note-content"})
        return {}

    recorder = CallRecorder()
    await _timed(node, {}, recorder)

    assert [c.name for c in recorder.calls] == ["generate-note-content"]
