"""annotate UI の HTTP 面。

画面は判断に要る材料（会話履歴・応答・事前分析の決定・該当 failure_mode の assertion）を
1 回の取得で受け取る。保存は store と同じ規則で弾き、不正な入力ではファイルを触らない。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from evals.tools.annotate.app import create_app
from tests.unit.evals.test_annotate_map_view import map_record


def _record(trace_id: str, **overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": trace_id,
        "schema_version": 3,
        "source": "real",
        "session": "2026-09-17-session",
        "dialogue_session_id": None,
        "turn": 3,
        "captured_at": "2026-09-17T06:00:00Z",
        "meta": {"model": "gpt-4.1-nano", "prompt_version": "generate_question@v4"},
        "input": {
            "conversation_history": [
                {"role": "user", "content": "トピック"},
                {"role": "assistant", "content": "説明してください"},
                {"role": "user", "content": "プロセスとは実行単位です"},
            ],
            "graph_state": {"topic": "トピック", "covered_aspects": [], "turn_count": 1},
        },
        "output": "その仕組みはどう動きますか？",
        "turn_decision": {"response_mode": "deepen", "selected_aspect": "実行単位", "error_summary": ""},
        "pass": None,
        "first_failure": None,
        "note": "",
        "annotated_at": None,
    }
    return record | overrides


@pytest.fixture
def dataset(tmp_path: Path) -> tuple[Path, Path, Path]:
    jsonl_path = tmp_path / "generate_questions.jsonl"
    records = [
        _record("rec-done", **{"pass": True, "note": "正例", "annotated_at": "2026-09-01T00:00:00Z"}),
        _record("rec-todo"),
    ]
    jsonl_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")

    golden_dir = tmp_path / "golden"
    golden_dir.mkdir()
    (golden_dir / "self_answered_question.yaml").write_text(
        "failure_mode: self_answered_question\n"
        "schema_version: 2\n"
        "status: active\n"
        "assertions:\n"
        "  - id: a1\n"
        "    type: judge\n"
        "    polarity: must_not\n"
        "    criterion: >\n"
        "      AI が自分の質問の答えを先に述べている。\n"
        "  - id: a5\n"
        "    type: deterministic\n"
        "    check: contains_generic_prompt_phrase\n"
        "    check_fingerprint: a9bd66a88432\n"
        "    polarity: must_not\n"
        "    criterion: >\n"
        "      一般化した促しを含んでいる。\n"
        "instances: []\n",
        encoding="utf-8",
    )

    rubric_dir = tmp_path / "rubric"
    rubric_dir.mkdir()
    (rubric_dir / "common.yaml").write_text(
        "schema_version: 1\n"
        "assertions:\n"
        "  - id: r1\n"
        "    type: judge\n"
        "    polarity: must_not\n"
        "    criterion: >\n"
        "      正しく述べた内容に解説を被せている。\n",
        encoding="utf-8",
    )
    return jsonl_path, golden_dir, rubric_dir


@pytest.fixture
def client(dataset: tuple[Path, Path, Path]) -> TestClient:
    jsonl_path, golden_dir, rubric_dir = dataset
    return TestClient(create_app(jsonl_path=jsonl_path, golden_dir=golden_dir, rubric_dir=rubric_dir))


def test_index_is_served(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "annotate" in response.text.lower()


def test_listing_groups_by_session_in_turn_order(tmp_path: Path, dataset: tuple[Path, Path, Path]) -> None:
    jsonl_path, golden_dir, rubric_dir = dataset
    records = [
        _record("b__t6", session="2026-09-17-b", turn=6),
        _record("a__t4", session="2026-09-01-a", turn=4, **{"pass": True, "annotated_at": "2026-09-01T00:00:00Z"}),
        _record("b__t4", session="2026-09-17-b", turn=4, **{"pass": False, "annotated_at": "2026-09-17T00:00:00Z"}),
        _record("a__t6", session="2026-09-01-a", turn=6),
    ]
    jsonl_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    client = TestClient(create_app(jsonl_path=jsonl_path, golden_dir=golden_dir, rubric_dir=rubric_dir))

    listed = client.get("/api/records").json()["records"]

    assert [r["id"] for r in listed] == ["a__t4", "a__t6", "b__t4", "b__t6"]


def test_listing_carries_the_session_topic(client: TestClient) -> None:
    records = client.get("/api/records").json()["records"]

    assert {r["topic"] for r in records} == {"トピック"}


def test_detail_carries_everything_needed_to_judge(client: TestClient) -> None:
    body = client.get("/api/records/rec-todo").json()

    assert body["output"] == "その仕組みはどう動きますか？"
    assert body["conversation_history"][-1]["content"] == "プロセスとは実行単位です"
    assert body["turn_decision"]["selected_aspect"] == "実行単位"
    assert body["record"]["meta"]["prompt_version"] == "generate_question@v4"
    assert body["record"]["topic"] == "トピック"
    assert [m["key"] for m in body["failure_modes"]] == sorted(m["key"] for m in body["failure_modes"])
    assert body["assertions"]["self_answered_question"][0]["id"] == "a1"


def test_detail_reports_deterministic_outcomes_without_a_failure(client: TestClient) -> None:
    body = client.get("/api/records/rec-todo").json()

    assert [o["fails"] for o in body["deterministic_outcomes"]] == [False]


def test_legacy_record_detail_has_no_depth_map(client: TestClient) -> None:
    body = client.get("/api/records/rec-todo").json()

    assert body["depth_map"] is None
    assert body["turn_decision"]["selected_aspect"] == "実行単位"


def test_map_record_detail_carries_the_depth_map_view(dataset: tuple[Path, Path, Path]) -> None:
    jsonl_path, golden_dir, rubric_dir = dataset
    map_base = map_record()
    record = _record("rec-map", turn_decision=map_base["turn_decision"])
    record["meta"] = map_base["meta"]
    record["input"]["graph_state"] = map_base["input"]["graph_state"] | {"topic": "トピック"}
    jsonl_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    client = TestClient(create_app(jsonl_path=jsonl_path, golden_dir=golden_dir, rubric_dir=rubric_dir))

    view = client.get("/api/records/rec-map").json()["depth_map"]

    assert view["decision"]["response_mode"] == "deepen"
    assert view["decision"]["injected_question"] == "a-reasoned"
    assert [a["stage_after"] for a in view["aspects"]] == ["defined", None]


def test_unknown_record_is_404(client: TestClient) -> None:
    assert client.get("/api/records/missing").status_code == 404
    assert client.put("/api/records/missing/annotation", json={"pass": True, "note": ""}).status_code == 404


def test_saving_updates_the_jsonl(client: TestClient, dataset: tuple[Path, Path, Path]) -> None:
    jsonl_path, _, _ = dataset

    response = client.put(
        "/api/records/rec-todo/annotation",
        json={"pass": False, "first_failure": "self_answered_question", "note": "負例"},
    )

    assert response.status_code == 200
    assert response.json()["record"]["annotated"] is True
    saved = json.loads(jsonl_path.read_text(encoding="utf-8").splitlines()[1])
    assert saved["pass"] is False
    assert saved["first_failure"] == "self_answered_question"
    assert saved["annotated_at"] is not None


def test_invalid_annotation_is_rejected_without_touching_the_file(
    client: TestClient, dataset: tuple[Path, Path, Path]
) -> None:
    jsonl_path, _, _ = dataset
    before = jsonl_path.read_bytes()

    response = client.put("/api/records/rec-todo/annotation", json={"pass": False, "note": ""})

    assert response.status_code == 422
    assert "first_failure" in " ".join(response.json()["detail"]["problems"])
    assert jsonl_path.read_bytes() == before


def test_unknown_payload_fields_are_rejected(client: TestClient) -> None:
    response = client.put("/api/records/rec-todo/annotation", json={"pass": True, "note": "", "output": "書換"})

    assert response.status_code == 422


def test_promotion_appends_the_instance_to_golden(client: TestClient, dataset: tuple[Path, Path, Path]) -> None:
    _, golden_dir, _ = dataset
    client.put("/api/records/rec-todo/annotation", json={"pass": True, "note": "正例"})

    response = client.post(
        "/api/records/rec-todo/promote",
        json={
            "failure_mode": "self_answered_question",
            "human_verdicts": {"a1": "pass", "a5": "pass", "r1": "pass"},
            "rationale": "1観点に絞った質問になっている。",
            "verified_by": "R-koma",
        },
    )

    assert response.status_code == 200
    assert response.json()["record"]["promoted_to"] == "self_answered_question"
    data = yaml.safe_load((golden_dir / "self_answered_question.yaml").read_text(encoding="utf-8"))
    assert [i["source_trace_id"] for i in data["instances"]] == ["rec-todo"]
    assert data["instances"][0]["human_verdicts"] == {"a1": "pass", "a5": "pass", "r1": "pass"}


def test_promoting_an_unannotated_record_is_rejected(client: TestClient, dataset: tuple[Path, Path, Path]) -> None:
    _, golden_dir, _ = dataset
    before = (golden_dir / "self_answered_question.yaml").read_bytes()

    response = client.post(
        "/api/records/rec-todo/promote",
        json={
            "failure_mode": "self_answered_question",
            "human_verdicts": {"a1": "pass", "a5": "pass", "r1": "pass"},
            "rationale": "根拠",
            "verified_by": "R-koma",
        },
    )

    assert response.status_code == 422
    assert "annotate" in " ".join(response.json()["detail"]["problems"])
    assert (golden_dir / "self_answered_question.yaml").read_bytes() == before


def test_detail_suggests_the_existing_reviewer(client: TestClient) -> None:
    assert client.get("/api/records/rec-todo").json()["default_verified_by"] == ""


def test_relabelling_a_promoted_instance(client: TestClient, dataset: tuple[Path, Path, Path]) -> None:
    _, golden_dir, _ = dataset
    client.put("/api/records/rec-todo/annotation", json={"pass": True, "note": "正例"})
    client.post(
        "/api/records/rec-todo/promote",
        json={
            "failure_mode": "self_answered_question",
            "human_verdicts": {"a1": "pass", "a5": "pass", "r1": "pass"},
            "rationale": "正例",
            "verified_by": "R-koma",
        },
    )

    verdicts = {"a1": "pass", "a5": "pass", "r1": "pass"}
    response = client.put("/api/records/rec-todo/verdicts", json={"human_verdicts": verdicts})

    assert response.status_code == 200
    assert response.json()["human_verdicts"] == verdicts
    assert client.get("/api/records/rec-todo").json()["promoted_verdicts"] == verdicts


def test_relabelling_a_record_that_is_not_in_golden_is_rejected(client: TestClient) -> None:
    verdicts = {"a1": "pass", "a5": "pass", "r1": "pass"}
    response = client.put("/api/records/rec-todo/verdicts", json={"human_verdicts": verdicts})

    assert response.status_code == 422
    assert "golden に無い" in " ".join(response.json()["detail"]["problems"])
