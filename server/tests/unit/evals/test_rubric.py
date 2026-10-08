"""共通 assertion（rubric）の読み込みと合流。

同じ criterion を failure_mode ごとに複製すると、片方だけ直したときに静かに食い違う。
合流は `record[\"assertions\"]` という一点で行い、由来を `scope` で残す。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.rubric import FAILURE_MODE_SCOPE, RUBRIC_SCOPE, load_rubric, merge_assertions


@pytest.fixture
def rubric_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "rubric"
    directory.mkdir()
    (directory / "common.yaml").write_text(
        "schema_version: 1\n"
        "assertions:\n"
        "  - id: r1\n"
        "    type: judge\n"
        "    polarity: must_not\n"
        "    criterion: >\n"
        "      共通の観点。\n",
        encoding="utf-8",
    )
    (directory / "_draft.yaml").write_text("assertions: []\n", encoding="utf-8")
    return directory


def test_underscore_files_are_skipped(rubric_dir: Path) -> None:
    assert [a["id"] for a in load_rubric(rubric_dir)] == ["r1"]


def test_merge_keeps_failure_mode_assertions_first_and_records_the_scope(rubric_dir: Path) -> None:
    own = [{"id": "a1", "type": "judge", "polarity": "must"}]

    merged = merge_assertions(own, load_rubric(rubric_dir))

    assert [a["id"] for a in merged] == ["a1", "r1"]
    assert [a["scope"] for a in merged] == [FAILURE_MODE_SCOPE, RUBRIC_SCOPE]


def test_merge_does_not_mutate_the_inputs(rubric_dir: Path) -> None:
    own = [{"id": "a1", "type": "judge", "polarity": "must"}]
    rubric = load_rubric(rubric_dir)

    merge_assertions(own, rubric)

    assert "scope" not in own[0]
    assert "scope" not in rubric[0]


def test_colliding_ids_are_refused(rubric_dir: Path) -> None:
    own = [{"id": "r1", "type": "judge", "polarity": "must"}]

    with pytest.raises(ValueError, match="r1"):
        merge_assertions(own, load_rubric(rubric_dir))


def test_the_shipped_rubric_declares_every_invariant() -> None:
    assertions = {a["id"]: a for a in load_rubric()}

    assert set(assertions) == {"r1", "r2", "r3", "r4"}
    assert assertions["r1"]["applies_when"].strip().startswith("ユーザーの直前の説明に")
    assert assertions["r2"]["check"] == "contains_generic_prompt_phrase"
    assert assertions["r3"]["polarity"] == "must_not"
    assert assertions["r4"]["check"] == "contains_stock_praise"
