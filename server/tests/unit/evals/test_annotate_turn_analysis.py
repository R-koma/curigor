from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from evals.tools.annotate import turn_analysis_store
from evals.tools.annotate.app import create_app

_LEAK = "判定の要約が漏れていないこと"
_DECISION = {"has_misconception": True, "user_intent": "partial_dont_know"}


def _source(record_id: str, topic: str = "スタック", decision: dict[str, Any] | None = _DECISION) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": record_id,
        "turn": 2,
        "meta": {"route": "map", "captured_by": "capture"},
        "input": {
            "conversation_history": [
                {"role": "assistant", "content": "スタックについて説明してみてください。"},
                {"role": "user", "content": "後入れ先出しのデータ構造だと思います。"},
            ],
            "graph_state": {
                "topic": topic,
                "depth_map": {"aspects": [{"id": "a1", "name": "LIFO", "is_core": True}]},
                "map_covered": [{"aspect_id": "a1", "reached_stage": "defined"}],
            },
        },
        "output": "応答",
    }
    if decision is not None:
        record["turn_decision"] = {**decision, "error_summary": _LEAK, "response_mode": "reinforce"}
    return record


def _row(row_id: str, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": row_id,
        "source": "real",
        "base": row_id,
        "expected": None,
        "unclear": [],
        "note": "",
        "annotated_at": None,
    }
    return row | overrides


def _handwritten(row_id: str, **overrides: Any) -> dict[str, Any]:
    return (
        _row(row_id, source="handwritten", base="s1", last_user_message="キューも同じです。", category="misconception")
        | overrides
    )


def _write(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return path


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "turn.jsonl",
        [
            _row("s1", expected={"has_misconception": False, "user_intent": "explanation"}),
            _row("s2"),
            _row("s3", expected={"has_misconception": True, "user_intent": "explanation"}),
            _handwritten("hw1"),
            _handwritten("hw2", expected={"has_misconception": True, "user_intent": "explanation"}),
        ],
    )


@pytest.fixture
def client(dataset: Path, tmp_path: Path) -> TestClient:
    partial = _source("s3", "ヒープ", decision=None)
    partial["turn_decision"] = {"has_misconception": True, "error_summary": _LEAK}
    sources = _write(tmp_path / "q.jsonl", [_source("s1"), _source("s2", "キュー", decision=None), partial])
    return TestClient(create_app(jsonl_path=sources, turn_analysis_jsonl_path=dataset))


def _label(**overrides: Any) -> dict[str, Any]:
    return {"has_misconception": True, "user_intent": "question", "unclear": [], "note": "", **overrides}


def test_save_label_rewrites_only_the_target_line(dataset: Path) -> None:
    before = dataset.read_text(encoding="utf-8").splitlines()

    turn_analysis_store.save_label(
        dataset,
        "s2",
        has_misconception=True,
        user_intent="question",
        unclear=[],
        note="混同",
        now=datetime(2026, 11, 15, tzinfo=UTC),
    )

    after = dataset.read_text(encoding="utf-8").splitlines()
    assert [after[i] for i in (0, 2, 3)] == [before[i] for i in (0, 2, 3)]
    updated = json.loads(after[1])
    assert updated["expected"] == {"has_misconception": True, "user_intent": "question"}
    assert updated["note"] == "混同"
    assert updated["annotated_at"] == "2026-11-15T00:00:00Z"


def test_unclear_fields_are_saved_as_none(dataset: Path) -> None:
    updated = turn_analysis_store.save_label(
        dataset, "s2", has_misconception=True, user_intent="question", unclear=["has_misconception"], note=""
    )

    assert updated["expected"] == {"has_misconception": None, "user_intent": "question"}
    assert updated["unclear"] == ["has_misconception"]


def test_a_field_that_is_not_unclear_needs_a_value(dataset: Path) -> None:
    with pytest.raises(turn_analysis_store.LabelError):
        turn_analysis_store.save_label(
            dataset, "s2", has_misconception=None, user_intent="question", unclear=[], note=""
        )
    with pytest.raises(turn_analysis_store.LabelError):
        turn_analysis_store.save_label(dataset, "s2", has_misconception=True, user_intent=None, unclear=[], note="")


@pytest.mark.parametrize(("user_intent", "unclear"), [("chat", []), ("question", ["tone"])])
def test_save_label_rejects_bad_values_without_writing(dataset: Path, user_intent: str, unclear: list[str]) -> None:
    before = dataset.read_text(encoding="utf-8")

    with pytest.raises(turn_analysis_store.LabelError):
        turn_analysis_store.save_label(
            dataset, "s2", has_misconception=True, user_intent=user_intent, unclear=unclear, note=""
        )

    assert dataset.read_text(encoding="utf-8") == before


def test_save_label_edits_the_message_of_a_handwritten_row_only(dataset: Path) -> None:
    updated = turn_analysis_store.save_label(
        dataset,
        "hw1",
        has_misconception=False,
        user_intent="question",
        unclear=[],
        note="",
        last_user_message=" 直した発言 ",
    )

    assert updated["last_user_message"] == "直した発言"
    with pytest.raises(turn_analysis_store.LabelError):
        turn_analysis_store.save_label(
            dataset, "hw1", has_misconception=False, user_intent="question", unclear=[], note="", last_user_message=" "
        )
    with pytest.raises(turn_analysis_store.LabelError):
        turn_analysis_store.save_label(
            dataset, "s2", has_misconception=False, user_intent="question", unclear=[], note="", last_user_message="x"
        )


def test_criteria_cuts_out_the_two_sections_of_the_production_prompt() -> None:
    criteria = turn_analysis_store.criteria()

    assert set(criteria) == {"has_misconception", "user_intent"}
    assert "exhausted" in criteria["user_intent"] and "end_session" in criteria["user_intent"]
    assert "誤り" in criteria["has_misconception"]
    assert "observations" not in criteria["has_misconception"]
    assert "has_misconception" not in criteria["user_intent"].split("\n")[0]


def test_list_puts_unlabeled_rows_first_and_never_returns_the_decision(client: TestClient) -> None:
    response = client.get("/api/turn-analysis/records")
    records = response.json()["records"]

    assert [r["id"] for r in records] == ["s2", "hw1", "s1", "s3", "hw2"]
    assert [r["labeled"] for r in records] == [False, False, True, True, True]
    assert "category" not in records[1]
    assert records[4]["category"] == "misconception"
    assert records[1]["last_user_message"].startswith("キューも同じ")
    assert _LEAK not in response.text


def test_unlabeled_detail_hides_the_model_decision(client: TestClient) -> None:
    unlabeled = client.get("/api/turn-analysis/records/s2")
    assert "model_decision" not in unlabeled.json()
    assert _LEAK not in unlabeled.text
    hand = client.get("/api/turn-analysis/records/hw1")
    assert "model_decision" not in hand.json()
    assert _LEAK not in hand.text


def test_detail_returns_what_the_annotator_reads(client: TestClient) -> None:
    body = client.get("/api/turn-analysis/records/s2").json()

    assert body["topic"] == "キュー"
    assert body["conversation"][-1]["content"] == "後入れ先出しのデータ構造だと思います。"
    assert body["map_progress"] == [{"name": "LIFO", "is_core": True, "stage": "定義済み"}]
    assert set(body["criteria"]) == {"has_misconception", "user_intent"}
    assert body["expected"] is None


def test_saving_reveals_the_decision_of_a_real_row(client: TestClient) -> None:
    response = client.put("/api/turn-analysis/records/s2/label", json=_label())
    assert response.status_code == 200
    assert response.json()["record"]["labeled"] is True

    body = client.get("/api/turn-analysis/records/s2").json()
    assert body["model_decision"] is None
    body = client.get("/api/turn-analysis/records/s1").json()
    assert body["model_decision"] == _DECISION


def test_a_handwritten_row_never_shows_the_decision(client: TestClient) -> None:
    body = client.get("/api/turn-analysis/records/hw2").json()

    assert "model_decision" not in body
    assert body["conversation"][-1]["content"] == "キューも同じです。"
    assert body["last_user_message"] == "キューも同じです。"


def test_put_label_edits_a_handwritten_message_and_rejects_it_for_real(client: TestClient, dataset: Path) -> None:
    ok = client.put("/api/turn-analysis/records/hw1/label", json=_label(last_user_message="書き直し"))
    assert ok.status_code == 200
    assert client.get("/api/turn-analysis/records/hw1").json()["conversation"][-1]["content"] == "書き直し"

    before = dataset.read_text(encoding="utf-8")
    bad = client.put("/api/turn-analysis/records/s2/label", json=_label(last_user_message="書き直し"))
    assert bad.status_code == 422
    assert dataset.read_text(encoding="utf-8") == before


def test_put_label_rejects_a_missing_value(client: TestClient, dataset: Path) -> None:
    before = dataset.read_text(encoding="utf-8")

    response = client.put("/api/turn-analysis/records/s2/label", json=_label(user_intent=None))

    assert response.status_code == 422
    assert dataset.read_text(encoding="utf-8") == before


def test_unknown_record_is_404(client: TestClient) -> None:
    assert client.get("/api/turn-analysis/records/nope").status_code == 404
    assert client.put("/api/turn-analysis/records/nope/label", json=_label()).status_code == 404


def test_turn_analysis_page_is_served(client: TestClient) -> None:
    response = client.get("/turn-analysis")

    assert response.status_code == 200
    assert "/api/turn-analysis/records" in response.text


def test_missing_dataset_lists_nothing(tmp_path: Path) -> None:
    client = TestClient(create_app(jsonl_path=tmp_path / "q.jsonl", turn_analysis_jsonl_path=tmp_path / "none.jsonl"))

    assert client.get("/api/turn-analysis/records").json() == {"records": []}


def test_the_aimed_category_of_a_handwritten_row_is_withheld_until_it_is_labeled(client: TestClient) -> None:
    unlabeled = client.get("/api/turn-analysis/records/hw1")
    labeled = client.get("/api/turn-analysis/records/hw2")

    assert "category" not in unlabeled.json()["record"]
    assert labeled.json()["record"]["category"] == "misconception"


def test_saving_a_handwritten_row_reveals_its_category(client: TestClient) -> None:
    client.put("/api/turn-analysis/records/hw1/label", json=_label())

    assert client.get("/api/turn-analysis/records/hw1").json()["record"]["category"] == "misconception"


def test_model_decision_omits_fields_the_old_record_did_not_store(client: TestClient) -> None:
    body = client.get("/api/turn-analysis/records/s3").json()

    assert body["model_decision"] == {"has_misconception": True}


def test_detail_says_how_many_messages_the_model_sees(client: TestClient) -> None:
    import inspect

    from graph.nodes._shared import recent_messages_block

    body = client.get("/api/turn-analysis/records/s2").json()

    assert body["model_context_messages"] == inspect.signature(recent_messages_block).parameters["limit"].default == 6


def test_page_draws_the_model_boundary_from_the_api_value(client: TestClient) -> None:
    page = client.get("/turn-analysis").text

    assert "ここから下がモデルに渡る範囲" in page
    assert "model_context_messages" in page
    assert "直近 6 件" not in page
