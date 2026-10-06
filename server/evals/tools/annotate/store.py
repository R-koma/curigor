"""正本 jsonl の annotate（`pass` / `first_failure` / `note` / `annotated_at`）の読み書き。

書き戻しは対象 1 行の置換に閉じる。`input` / `output` / `meta` / `turn_decision` は golden の
写しとバイト比較されるため、UI からは触れない。

golden は `evals.eval.load_golden_records()` を使わずここで読む。あちらは `status: active` で
絞るが、昇格済み instance との `pass` 不一致は status に関わらず起きる。
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

from evals.checks import run_check
from evals.golden_yaml import dump_instance_block
from evals.rubric import RUBRIC_DIR, RUBRIC_SCOPE, load_rubric, merge_assertions
from evals.taxonomy import FAILURE_MODES

_EVALS_DIR = Path(__file__).resolve().parents[2]
DEFAULT_JSONL_PATH = _EVALS_DIR / "datasets" / "generate_questions.jsonl"
DEFAULT_GOLDEN_DIR = _EVALS_DIR / "datasets" / "golden"

ANNOTATION_KEYS = ("pass", "first_failure", "note", "annotated_at")

_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_ASSERTION_KEYS = ("id", "type", "polarity", "criterion", "applies_when", "check", "scope")

_NOT_APPLICABLE = "na"
_VALID_VERDICTS = frozenset({"pass", "fail", _NOT_APPLICABLE})
_EMPTY_INSTANCES = re.compile(r"^instances:[ \t]*(\[[ \t]*\])?[ \t]*$\n?", re.MULTILINE)
_INSTANCE_MARKER = "  - source_trace_id:"
_VERDICT_INDENT = 4


@dataclass(frozen=True)
class Annotation:
    verdict: bool | None
    first_failure: str | None
    note: str


@dataclass(frozen=True)
class GoldenInstance:
    failure_mode: str
    path: Path
    verdict: bool | None
    human_verdicts: dict[str, str]


@dataclass(frozen=True)
class DeterministicOutcome:
    assertion_id: str
    failure_mode: str
    check: str
    fails: bool
    detail: str


@dataclass(frozen=True)
class Promotion:
    failure_mode: str
    human_verdicts: dict[str, str]
    rationale: str
    verified_by: str


class _ProblemsError(ValueError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__(" / ".join(problems))
        self.problems = problems


class AnnotationError(_ProblemsError):
    pass


class PromotionError(_ProblemsError):
    pass


class VerdictError(_ProblemsError):
    pass


def load_records(path: Path = DEFAULT_JSONL_PATH) -> list[dict[str, Any]]:
    return [json.loads(line) for line in _lines(path) if line.strip()]


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def _golden_files(golden_dir: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    for path in sorted(golden_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        # instance がまだ 1 件も無いファイルは `instances:` が None になる（起票直後の状態）
        data["instances"] = data["instances"] or []
        yield path, data


def golden_instances(golden_dir: Path = DEFAULT_GOLDEN_DIR) -> dict[str, GoldenInstance]:
    return {
        instance["source_trace_id"]: GoldenInstance(
            failure_mode=data["failure_mode"],
            path=path,
            verdict=instance.get("pass"),
            human_verdicts=instance.get("human_verdicts") or {},
        )
        for path, data in _golden_files(golden_dir)
        for instance in data["instances"]
    }


def assertions_by_failure_mode(
    golden_dir: Path = DEFAULT_GOLDEN_DIR, rubric_dir: Path = RUBRIC_DIR
) -> dict[str, list[dict[str, Any]]]:
    rubric = load_rubric(rubric_dir)
    return {
        data["failure_mode"]: [
            {key: _clean(assertion[key]) for key in _ASSERTION_KEYS if key in assertion}
            for assertion in merge_assertions(data["assertions"], rubric)
        ]
        for _, data in _golden_files(golden_dir)
    }


def _clean(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


def deterministic_outcomes(
    output: str,
    golden_dir: Path = DEFAULT_GOLDEN_DIR,
    rubric_dir: Path = RUBRIC_DIR,
    conversation_history: Sequence[Mapping[str, str]] = (),
) -> list[DeterministicOutcome]:
    """deterministic assertion をこの出力に適用した結果。rubric 側も含める。

    UI は人間が `pass` を選ぶまでこれを表示しない。判定を先に見せると、人間ラベルが実装の写しに
    なり、混同行列（deterministic の outcome も含む）の一致率が自明に 100% になる。
    """
    outcomes: list[DeterministicOutcome] = []
    seen: set[tuple[str, str]] = set()
    for owner, assertions in _all_assertions(golden_dir, rubric_dir):
        for assertion in assertions:
            if assertion["type"] != "deterministic":
                continue
            key = (assertion["check"], assertion["polarity"])
            if key in seen:
                continue
            seen.add(key)
            result = run_check(assertion["check"], output, conversation_history)
            outcomes.append(
                DeterministicOutcome(
                    assertion_id=assertion["id"],
                    failure_mode=owner,
                    check=assertion["check"],
                    fails=result.holds if assertion["polarity"] == "must_not" else not result.holds,
                    detail=result.detail,
                )
            )
    return outcomes


def _all_assertions(golden_dir: Path, rubric_dir: Path) -> list[tuple[str, list[dict[str, Any]]]]:
    """(所属, assertion 群) の列。rubric は failure_mode に属さないので先頭に 1 度だけ置く。"""
    owned = [(data["failure_mode"], data["assertions"]) for _, data in _golden_files(golden_dir)]
    return [(RUBRIC_SCOPE, load_rubric(rubric_dir)), *owned]


def validate_annotation(annotation: Annotation, golden: GoldenInstance | None) -> list[str]:
    problems: list[str] = []
    if annotation.first_failure is not None and annotation.first_failure not in FAILURE_MODES:
        problems.append(
            f"first_failure={annotation.first_failure!r} が evals.taxonomy.FAILURE_MODES に無い"
            f"（候補: {', '.join(sorted(FAILURE_MODES))}）"
        )
    if annotation.verdict is False and annotation.first_failure is None:
        problems.append("pass=false のレコードは first_failure が必須")
    if annotation.verdict is not False and annotation.first_failure is not None:
        problems.append("pass=false 以外のレコードに first_failure は付けられない")
    if golden is not None and golden.verdict != annotation.verdict:
        problems.append(
            f"golden の instance（{golden.path.name}）が pass={golden.verdict!r} なので、"
            f"jsonl 側だけを pass={annotation.verdict!r} に変えられない"
        )
    return problems


def apply_annotation(record: dict[str, Any], annotation: Annotation, *, now: datetime) -> dict[str, Any]:
    return record | {
        "pass": annotation.verdict,
        "first_failure": annotation.first_failure,
        "note": annotation.note,
        "annotated_at": None if annotation.verdict is None else now.strftime(_TIMESTAMP_FORMAT),
    }


def save_annotation(
    path: Path,
    trace_id: str,
    annotation: Annotation,
    *,
    golden_dir: Path = DEFAULT_GOLDEN_DIR,
    now: datetime | None = None,
) -> dict[str, Any]:
    lines = _lines(path)
    index = _index_of(lines, trace_id, path)
    problems = validate_annotation(annotation, golden_instances(golden_dir).get(trace_id))
    if problems:
        raise AnnotationError(problems)

    updated = apply_annotation(json.loads(lines[index]), annotation, now=now or datetime.now(UTC))
    lines[index] = json.dumps(updated, ensure_ascii=False) + "\n"
    _write_atomically(path, "".join(lines))
    return updated


def default_verified_by(golden_dir: Path = DEFAULT_GOLDEN_DIR) -> str:
    reviewers = Counter(
        instance["verified_by"]
        for _, data in _golden_files(golden_dir)
        for instance in data["instances"]
        if instance.get("verified_by")
    )
    return reviewers.most_common(1)[0][0] if reviewers else ""


def validate_verdicts(
    instance_pass: bool | None,
    verdicts: dict[str, str],
    assertions: list[dict[str, Any]],
) -> list[str]:
    declared = {assertion["id"]: assertion for assertion in assertions}
    problems: list[str] = []
    if missing := sorted(set(declared) - set(verdicts)):
        problems.append(f"human_verdicts にラベルが無い assertion: {', '.join(missing)}")
    if extra := sorted(set(verdicts) - set(declared)):
        problems.append(f"assertions に無い id へのラベル: {', '.join(extra)}")
    problems.extend(
        f"{assertion_id}: 不正な verdict {verdict!r}（{'/'.join(sorted(_VALID_VERDICTS))} のみ）"
        for assertion_id, verdict in sorted(verdicts.items())
        if verdict not in _VALID_VERDICTS
    )
    problems.extend(
        f"{assertion_id}: applies_when を持たない assertion に na は付けられない"
        for assertion_id, verdict in sorted(verdicts.items())
        if verdict == _NOT_APPLICABLE and assertion_id in declared and not declared[assertion_id].get("applies_when")
    )

    scored = [v for v in verdicts.values() if v in {"pass", "fail"}]
    if instance_pass is True and "fail" in scored:
        problems.append("pass=true のレコードに fail の verdict は付けられない")
    if instance_pass is False and scored and "fail" not in scored:
        problems.append(
            "pass=false なのに fail が 1 つも無い。この失敗を捉える assertion が無いので、"
            "別の failure_mode を選ぶか assertion を先に足す"
        )
    return problems


def update_verdicts(
    golden_dir: Path, trace_id: str, verdicts: dict[str, str], *, rubric_dir: Path = RUBRIC_DIR
) -> Path:
    """昇格済み instance の `human_verdicts` ブロックだけを差し替える。

    criterion は folded scalar で折り返しが原文に依存するため、ここでは触らない。差し替えるのは
    `human_verdicts:` の直下の行だけで、instance の他のフィールドと他の instance は動かさない。
    """
    instance = golden_instances(golden_dir).get(trace_id)
    if instance is None:
        raise VerdictError([f"{trace_id} は golden に無いので付け直せない（先に昇格する）"])

    assertions = assertions_by_failure_mode(golden_dir, rubric_dir)[instance.failure_mode]
    if problems := validate_verdicts(instance.verdict, verdicts, assertions):
        raise VerdictError(problems)

    lines = instance.path.read_text(encoding="utf-8").splitlines(keepends=True)
    start, stop = _verdict_span(lines, trace_id, instance.path)
    block = [f"{' ' * _VERDICT_INDENT}human_verdicts:\n"]
    block += [f"{' ' * (_VERDICT_INDENT + 2)}{a['id']}: {verdicts[a['id']]}\n" for a in assertions]
    _write_atomically(instance.path, "".join(lines[:start] + block + lines[stop:]))
    return instance.path


def _verdict_span(lines: list[str], trace_id: str, path: Path) -> tuple[int, int]:
    """`human_verdicts:` の行から、同じかより浅いインデントの次の行までの範囲。"""
    start = next(
        (
            i
            for i, line in enumerate(lines)
            if line.startswith(f"{' ' * _VERDICT_INDENT}human_verdicts:") and _owning_trace_id(lines, i) == trace_id
        ),
        None,
    )
    if start is None:
        raise VerdictError([f"{path.name}: {trace_id} の human_verdicts ブロックを見つけられない"])
    stop = next(
        (
            i
            for i in range(start + 1, len(lines))
            if lines[i].strip() and len(lines[i]) - len(lines[i].lstrip(" ")) <= _VERDICT_INDENT
        ),
        len(lines),
    )
    return start, stop


def _owning_trace_id(lines: list[str], index: int) -> str | None:
    for line in reversed(lines[: index + 1]):
        if line.startswith(_INSTANCE_MARKER):
            return line[len(_INSTANCE_MARKER) :].strip().strip("\"'")
    return None


def validate_promotion(
    record: dict[str, Any],
    promotion: Promotion,
    assertions: list[dict[str, Any]] | None,
    *,
    already_promoted: GoldenInstance | None,
) -> list[str]:
    problems: list[str] = []
    if record["pass"] is None:
        problems.append("まだ annotate されていないレコードは昇格できない（pass を先に決める）")
    if already_promoted is not None:
        problems.append(f"既に golden にある（{already_promoted.path.name}）")
    if assertions is None:
        problems.append(
            f"failure_mode={promotion.failure_mode!r} の golden ファイルが無い。"
            "assertion の起草は人手の作業なので、`_TEMPLATE.yaml` を元に先にファイルを作る"
        )
        return problems

    problems.extend(validate_verdicts(record["pass"], promotion.human_verdicts, assertions))
    if not promotion.rationale.strip():
        problems.append("rationale は必須（なぜ失敗か / なぜ良いかを人間の言葉で残す）")
    if not promotion.verified_by.strip():
        problems.append("verified_by は必須")
    return problems


def promote_to_golden(
    jsonl_path: Path,
    golden_dir: Path,
    trace_id: str,
    promotion: Promotion,
    *,
    rubric_dir: Path = RUBRIC_DIR,
    today: date | None = None,
) -> Path:
    """正本のレコードを golden の `instances:` へ 1 件追記する。

    YAML は読み込んで書き直さず末尾へ足すだけにする。pyyaml の round-trip は `>` の折り返しと
    コメントを落とすため、既存の assertion 定義と他の instance を壊す。
    """
    record = next((r for r in load_records(jsonl_path) if r["id"] == trace_id), None)
    if record is None:
        raise LookupError(f"unknown trace id: {trace_id} not in {jsonl_path}")

    assertions = assertions_by_failure_mode(golden_dir, rubric_dir).get(promotion.failure_mode)
    problems = validate_promotion(
        record, promotion, assertions, already_promoted=golden_instances(golden_dir).get(trace_id)
    )
    if problems:
        raise PromotionError(problems)

    path = golden_dir / f"{promotion.failure_mode}.yaml"
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if (last_key := list(data)[-1]) != "instances":
        raise PromotionError([f"{path.name}: `instances` が最後のキーでない（末尾は {last_key!r}）ので追記できない"])

    block = dump_instance_block(
        record,
        human_verdicts=promotion.human_verdicts,
        rationale=promotion.rationale.strip(),
        verified_by=promotion.verified_by.strip(),
        created_at=today or datetime.now(UTC).date(),
    )
    if data["instances"]:
        updated = f"{text}\n{block}"
    else:
        empty = _EMPTY_INSTANCES.search(text)
        if empty is None:
            raise PromotionError([f"{path.name}: 空の `instances:` 行を見つけられないので追記できない"])
        updated = text[: empty.start()] + "instances:\n" + block
    _write_atomically(path, updated)
    return path


def _index_of(lines: list[str], trace_id: str, path: Path) -> int:
    for index, line in enumerate(lines):
        if line.strip() and json.loads(line)["id"] == trace_id:
            return index
    raise LookupError(f"unknown trace id: {trace_id} not in {path}")


def _write_atomically(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as tmp:
        tmp.write(text)
        temp_path = Path(tmp.name)
    os.replace(temp_path, path)
