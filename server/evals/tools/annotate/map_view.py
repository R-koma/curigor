"""地図に沿った経路のレコードを、annotate 画面向けの表示用の値に組み直す（読み取りだけ）。"""

from __future__ import annotations

from typing import Any

from graph.depth_map import STAGE_LABELS, next_stage, question_for

MAP_ROUTE = "map"


def map_view(record: dict[str, Any]) -> dict[str, Any] | None:
    if (record.get("meta") or {}).get("route") != MAP_ROUTE:
        return None
    graph_state = record["input"]["graph_state"]
    if not graph_state.get("depth_map"):
        return None

    decision = record.get("turn_decision")
    before_map = graph_state["depth_map"]
    after_map = (decision or {}).get("depth_map") or before_map
    before = {c["aspect_id"]: c["reached_stage"] for c in graph_state.get("map_covered") or []}
    after = {c["aspect_id"]: c["reached_stage"] for c in decision.get("map_covered") or []} if decision else before
    before_ids = {a["id"] for a in before_map["aspects"]}
    selected_id = (decision or {}).get("selected_aspect_id") or ""

    aspects = [
        {
            "id": aspect["id"],
            "name": aspect["name"],
            "is_core": aspect["is_core"],
            "stage_before": before.get(aspect["id"]),
            "stage_after": after.get(aspect["id"]),
            "added": aspect["id"] not in before_ids,
            "selected": aspect["id"] == selected_id,
            "defined_question": aspect["defined_question"],
            "reasoned_question": aspect["reasoned_question"],
            "applied_question": aspect["applied_question"],
        }
        for aspect in after_map["aspects"]
    ]

    return {
        "aspects": aspects,
        "stage_labels": STAGE_LABELS,
        "decision": _decision_view(decision, after_map, after) if decision else None,
        "wrap_up_offered": bool(graph_state.get("wrap_up_offered", False)),
        "turn_count": graph_state.get("turn_count"),
    }


def _decision_view(decision: dict[str, Any], depth_map: dict[str, Any], reached: dict[str, Any]) -> dict[str, Any]:
    selected_id = decision.get("selected_aspect_id") or ""
    aspect = next((a for a in depth_map["aspects"] if a["id"] == selected_id), None)
    injected_stage = next_stage(reached.get(selected_id)) if aspect else None
    return {
        "response_mode": decision.get("response_mode"),
        "selected_aspect_id": selected_id,
        "has_misconception": decision.get("has_misconception"),
        "error_summary": decision.get("error_summary") or "",
        "wrap_up": bool(decision.get("wrap_up", False)),
        "injected_stage": injected_stage,
        "injected_question": question_for(aspect, injected_stage) if aspect and injected_stage else None,
    }
