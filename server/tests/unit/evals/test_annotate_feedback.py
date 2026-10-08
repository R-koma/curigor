from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from evals.tools.annotate import feedback_store
from evals.tools.annotate.app import create_app


def _record(record_id: str, **overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": record_id,
        "schema_version": 1,
        "source": "real",
        "session": "2026-10-08-abcd1234",
        "session_type": "learning",
        "dialogue_session_id": "00000000-0000-0000-0000-000000000001",
        "meta": {"prompt_fingerprint": "x", "route": "map"},
        "input": {
            "topic": "プロセス",
            "conversation": [{"role": "human", "content": "プロセス"}],
            "note_text": "トピック: プロセス\n\n本文",
            "aspect_map": {"root": "プロセス", "aspects": [{"name": "実行単位", "children": [{"name": "PID"}]}]},
            "depth_map": {
                "aspects": [{"id": "a1", "name": "実行単位", "is_core": True}, {"id": "a2", "name": "状態"}]
            },
            "map_covered": [{"aspect_id": "a1", "reached_stage": "defined"}],
        },
        "output": {"understanding_level": "medium", "strengths": ["s"], "improvements": [{"text": "i"}]},
        "human_level": None,
        "note": "",
        "annotated_at": None,
    }
    return record | overrides


@pytest.fixture
def jsonl(tmp_path: Path) -> Path:
    path = tmp_path / "feedback.jsonl"
    records = [_record("a__feedback"), _record("b__feedback", human_level="low", annotated_at="2026-10-08T00:00:00Z")]
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    return path


@pytest.fixture
def client(jsonl: Path, tmp_path: Path) -> TestClient:
    return TestClient(create_app(jsonl_path=tmp_path / "q.jsonl", feedback_jsonl_path=jsonl))


def test_level_criteria_is_the_production_rubric() -> None:
    criteria = feedback_store.level_criteria()

    assert [line.split(":")[0] for line in criteria.splitlines()] == ["- high", "- medium", "- low"]


def test_save_label_rewrites_only_the_target_line(jsonl: Path) -> None:
    before = jsonl.read_text(encoding="utf-8").splitlines()

    feedback_store.save_label(jsonl, "a__feedback", "low", "浅い", now=datetime(2026, 10, 8, tzinfo=UTC))

    after = jsonl.read_text(encoding="utf-8").splitlines()
    assert after[1] == before[1]
    updated = json.loads(after[0])
    assert updated["human_level"] == "low"
    assert updated["note"] == "浅い"
    assert updated["annotated_at"] == "2026-10-08T00:00:00Z"
    assert updated["input"] == json.loads(before[0])["input"]


def test_clearing_the_label_clears_the_timestamp(jsonl: Path) -> None:
    updated = feedback_store.save_label(jsonl, "b__feedback", None, "")

    assert updated["annotated_at"] is None


def test_save_label_rejects_an_unknown_level(jsonl: Path) -> None:
    with pytest.raises(feedback_store.LabelError):
        feedback_store.save_label(jsonl, "a__feedback", "great", "")


def test_map_progress_shows_the_stage_of_each_aspect() -> None:
    progress = feedback_store.map_progress(_record("a")["input"])

    assert progress == [
        {"name": "実行単位", "is_core": True, "stage": "定義済み"},
        {"name": "状態", "is_core": False, "stage": None},
    ]


def test_map_progress_is_none_without_a_depth_map() -> None:
    assert feedback_store.map_progress({"topic": "t"}) is None


def test_list_hides_the_llm_level_until_labeled(client: TestClient) -> None:
    records = {r["id"]: r for r in client.get("/api/feedback/records").json()["records"]}

    assert records["a__feedback"]["llm_level"] is None
    assert records["b__feedback"]["llm_level"] == "medium"
    assert records["b__feedback"]["annotated"] is True


def test_detail_returns_what_the_annotator_reads(client: TestClient) -> None:
    body = client.get("/api/feedback/records/a__feedback").json()

    assert body["input"]["note_text"].startswith("トピック: プロセス")
    assert body["note_aspects"] == [{"name": "実行単位", "depth": 0}, {"name": "PID", "depth": 1}]
    assert body["map_progress"][0]["stage"] == "定義済み"
    assert "high:" in body["criteria"]


def test_put_label_saves_and_returns_the_summary(client: TestClient, jsonl: Path) -> None:
    response = client.put("/api/feedback/records/a__feedback/label", json={"human_level": "low", "note": " 浅い "})

    assert response.status_code == 200
    assert response.json()["record"]["llm_level"] == "medium"
    assert json.loads(jsonl.read_text(encoding="utf-8").splitlines()[0])["note"] == "浅い"


def test_put_label_rejects_an_unknown_level_without_writing(client: TestClient, jsonl: Path) -> None:
    before = jsonl.read_text(encoding="utf-8")

    response = client.put("/api/feedback/records/a__feedback/label", json={"human_level": "great"})

    assert response.status_code == 422
    assert jsonl.read_text(encoding="utf-8") == before


def test_unknown_record_is_404(client: TestClient) -> None:
    assert client.get("/api/feedback/records/nope").status_code == 404


def test_feedback_page_is_served(client: TestClient) -> None:
    response = client.get("/feedback")

    assert response.status_code == 200
    assert "/api/feedback/records" in response.text


def test_missing_dataset_lists_nothing(tmp_path: Path) -> None:
    client = TestClient(create_app(jsonl_path=tmp_path / "q.jsonl", feedback_jsonl_path=tmp_path / "none.jsonl"))

    assert client.get("/api/feedback/records").json() == {"records": []}
