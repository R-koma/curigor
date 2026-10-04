"""地図に沿った経路のレコードの表示用の値（annotate 画面）。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from evals.tools.annotate.map_view import map_view


def _aspect(aspect_id: str, *, is_core: bool = True) -> dict[str, Any]:
    return {
        "id": aspect_id,
        "name": aspect_id,
        "is_core": is_core,
        "defined_question": f"{aspect_id}-defined",
        "reasoned_question": f"{aspect_id}-reasoned",
        "applied_question": f"{aspect_id}-applied",
    }


def map_record(**decision_overrides: Any) -> dict[str, Any]:
    depth_map = {"topic": "t", "aspects": [_aspect("a"), _aspect("b", is_core=False)]}
    decision: dict[str, Any] = {
        "response_mode": "deepen",
        "selected_aspect": "a",
        "selected_aspect_id": "a",
        "has_misconception": False,
        "error_summary": "",
        "wrap_up": False,
        "depth_map": deepcopy(depth_map),
        "map_covered": [{"aspect_id": "a", "reached_stage": "defined"}],
    }
    return {
        "meta": {"route": "map"},
        "input": {
            "graph_state": {
                "depth_map": depth_map,
                "map_covered": [{"aspect_id": "a", "reached_stage": "mentioned"}],
                "wrap_up_offered": False,
                "turn_count": 2,
            }
        },
        "turn_decision": decision | decision_overrides,
    }


def test_legacy_record_has_no_map_view() -> None:
    record = map_record()
    record["meta"] = {}

    assert map_view(record) is None


def test_record_without_a_depth_map_has_no_map_view() -> None:
    record = map_record()
    del record["input"]["graph_state"]["depth_map"]

    assert map_view(record) is None


def test_stages_before_and_after_come_from_map_covered() -> None:
    view = map_view(map_record())
    assert view is not None

    a, b = view["aspects"]
    assert (a["stage_before"], a["stage_after"]) == ("mentioned", "defined")
    assert (b["stage_before"], b["stage_after"]) == (None, None)
    assert view["turn_count"] == 2


def test_injected_question_is_the_next_stage_after_the_merge() -> None:
    view = map_view(map_record())
    assert view is not None

    assert view["decision"]["injected_stage"] == "reasoned"
    assert view["decision"]["injected_question"] == "a-reasoned"
    assert [a["selected"] for a in view["aspects"]] == [True, False]


def test_aspect_added_by_the_turn_is_flagged() -> None:
    record = map_record()
    grown = deepcopy(record["turn_decision"]["depth_map"])
    grown["aspects"].append(_aspect("c", is_core=False))
    record["turn_decision"]["depth_map"] = grown
    record["turn_decision"]["selected_aspect_id"] = "c"

    view = map_view(record)
    assert view is not None

    assert [a["added"] for a in view["aspects"]] == [False, False, True]
    assert view["decision"]["injected_question"] == "c-defined"


def test_turn_without_analysis_keeps_the_stages_before() -> None:
    record = map_record()
    record["turn_decision"] = None

    view = map_view(record)
    assert view is not None

    assert view["decision"] is None
    assert view["aspects"][0]["stage_after"] == "mentioned"
    assert not any(a["selected"] for a in view["aspects"])


def test_empty_selection_has_no_injected_question() -> None:
    view = map_view(map_record(selected_aspect_id=""))
    assert view is not None

    assert view["decision"]["injected_question"] is None
    assert view["decision"]["injected_stage"] is None
