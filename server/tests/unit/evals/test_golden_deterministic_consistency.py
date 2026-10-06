"""golden の deterministic assertion が、実際の check 関数の判定と矛盾しないことを保証する。

過去に「主導的な質問が1つだけである」assertion が疑問符ベースの実装と人間ラベルで
恒常的に矛盾していた（#292 で削除）。同じ問題を二度と golden にコミットしないための回帰テスト。

判定対象は jsonl（正本）の `output`。golden YAML の `observed_output` は人間が読むための写しで、
runner もこのテストも参照しない。

deterministic assertion は rubric 側にあるので、runner と同じく合流させてから検査する
（golden ファイルだけを見ると検査対象が 0 件になり、テストが静かに空回りする）。
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any

import yaml

from evals.checks import check_fingerprint, run_check
from evals.rubric import load_rubric, merge_assertions

_DATASETS_DIR = Path(__file__).resolve().parents[3] / "evals" / "datasets"
_GOLDEN_DIR = _DATASETS_DIR / "golden"
_JSONL_PATH = _DATASETS_DIR / "generate_questions.jsonl"


def _passed(polarity: str, holds: bool) -> bool:
    return holds if polarity == "must" else not holds


def _load_source_outputs() -> dict[str, str]:
    outputs: dict[str, str] = {}
    with open(_JSONL_PATH, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record: dict[str, Any] = json.loads(line)
            outputs[record["id"]] = record["output"]
    return outputs


def _load_golden_files() -> list[dict[str, Any]]:
    files = []
    for path in sorted(glob.glob(str(_GOLDEN_DIR / "*.yaml"))):
        if Path(path).name.startswith("_"):
            continue
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        data["assertions"] = merge_assertions(data["assertions"], load_rubric())
        data["_path"] = path
        files.append(data)
    return files


def test_every_instance_resolves_to_a_source_trace() -> None:
    outputs = _load_source_outputs()
    missing: list[str] = []
    for data in _load_golden_files():
        for instance in data["instances"] or []:
            if instance["source_trace_id"] not in outputs:
                missing.append(
                    f"{data['_path']}: source_trace_id={instance['source_trace_id']!r} not in {_JSONL_PATH}"
                )
    assert not missing, "\n".join(missing)


def test_deterministic_assertions_match_human_verdicts() -> None:
    outputs = _load_source_outputs()
    mismatches: list[str] = []
    for data in _load_golden_files():
        deterministic = {a["id"]: a for a in data["assertions"] if a["type"] == "deterministic"}
        if not deterministic:
            continue
        for instance in data["instances"] or []:
            observed_output = outputs[instance["source_trace_id"]]
            for assertion_id, assertion in deterministic.items():
                actual = instance["human_verdicts"][assertion_id]
                if actual == "na":
                    continue
                outcome = run_check(assertion["check"], observed_output, instance["input"]["conversation_history"])
                expected = "pass" if _passed(assertion["polarity"], outcome.holds) else "fail"
                if expected != actual:
                    mismatches.append(
                        f"{data['_path']}: instance={instance['source_trace_id']} "
                        f"assertion={assertion_id} check says {expected!r}, human_verdicts says {actual!r} "
                        f"({outcome.detail})"
                    )
    assert not mismatches, "\n".join(mismatches)


def test_deterministic_assertion_fingerprints_match_implementation() -> None:
    stale: list[str] = []
    for data in _load_golden_files():
        for assertion in data["assertions"]:
            if assertion["type"] != "deterministic":
                continue
            current = check_fingerprint(assertion["check"])
            if assertion.get("check_fingerprint") != current:
                stale.append(
                    f"{data['_path']}: assertion={assertion['id']} check={assertion['check']} "
                    f"recorded={assertion.get('check_fingerprint')!r} current={current!r}"
                )
    assert not stale, "\n".join(stale)
