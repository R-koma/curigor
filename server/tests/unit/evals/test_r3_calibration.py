"""固定した境界例の構成を保証する。LLMの判定品質は実API評価で別途確認する。"""

from pathlib import Path

import yaml


def test_calibration_covers_both_directions_in_each_dialogue_category() -> None:
    path = Path(__file__).resolve().parents[3] / "evals/datasets/calibration/r3_application.yaml"
    data = yaml.safe_load(path.read_text())
    cases = data["cases"]
    assert len(cases) == len({case["id"] for case in cases}) == 12
    assert "verified against the r3 criterion" in data["label_provenance"]
    assert {case["category"] for case in cases} == {"correction", "unknown", "dialogue"}
    for category in ("correction", "unknown", "dialogue"):
        selected = [case for case in cases if case["category"] == category]
        assert sorted(case["expected_r3"] for case in selected) == ["fail", "fail", "pass", "pass"]
        assert all(case["conversation_history"] and case["output"] and case["rationale"] for case in selected)
