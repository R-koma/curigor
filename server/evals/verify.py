"""確認待ちの項目（`evals/pending/<issue>.yaml`）を、eval のレポートと照合する。

API は呼ばない。レポートの実行条件が項目と合わなければ「対象外」とし、そろえるためのコマンドを出す。
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from evals.golden_yaml import dump_yaml
from evals.taxonomy import LEGACY_ROUTE, MAP_ROUTE, ROUTE_CHOICES
from graph.prompts.map_question import MAP_PROMPT_FINGERPRINT
from graph.prompts.question import PROMPT_FINGERPRINT

EVALS_DIR = Path(__file__).parent
PENDING_DIR = EVALS_DIR / "pending"

UNCHECKED = "未確認"
PASSED = "合格"
FAILED = "不合格"
TO_READ = "人が読む"
NOT_COVERED = "対象外"
STATUSES = (UNCHECKED, PASSED, FAILED, TO_READ, NOT_COVERED)
SETTLED = (PASSED, FAILED)

DEFAULT_TOLERANCE = 2
MODES = ("regression", "scoring")
REPLAY_MODES = ("full", "pinned")
ITEM_KEYS = frozenset(
    {"id", "run", "target", "value", "equals", "expect", "read", "status", "checked_on", "report", "result"}
)
CALIBRATION_STAGES = ("final", "screen")


def current_fingerprints() -> dict[str, str]:
    return {"map_prompt_fingerprint": MAP_PROMPT_FINGERPRINT, "prompt_fingerprint": PROMPT_FINGERPRINT}


def load_pending(pending_dir: Path = PENDING_DIR) -> list[tuple[Path, dict[str, Any]]]:
    return [(path, yaml.safe_load(path.read_text(encoding="utf-8"))) for path in sorted(pending_dir.glob("*.yaml"))]


def save_pending(path: Path, document: dict[str, Any]) -> None:
    path.write_text(dump_yaml(document), encoding="utf-8")


def document_problems(path: Path, document: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if not isinstance(document.get("issue"), int):
        return [f"{path.name}: issue（番号）が無い"]
    if path.stem != str(document["issue"]):
        problems.append(f"{path.name}: ファイル名は issue の番号（{document['issue']}.yaml）にする")
    if not isinstance(document.get("summary"), str) or not document["summary"]:
        problems.append(f"{path.name}: summary が無い")
    items = document.get("items")
    if not isinstance(items, list) or not items:
        return [*problems, f"{path.name}: items が無い"]
    ids = [item.get("id") for item in items]
    if len(set(ids)) != len(ids):
        problems.append(f"{path.name}: item の id が重複している")
    problems.extend(f"{path.name}#{item.get('id')}: {p}" for item in items for p in item_problems(item))
    return problems


def item_problems(item: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if unknown := sorted(set(item) - ITEM_KEYS):
        problems.append(f"知らないキー: {unknown}")
    if not isinstance(item.get("id"), str):
        problems.append("id が無い")
    if item.get("status") not in STATUSES:
        problems.append(f"status は {STATUSES} のどれか")
    run = item.get("run")
    if not isinstance(run, dict):
        return [*problems, "run が無い"]
    mode = run.get("mode")
    if mode not in MODES:
        problems.append(f"run.mode は {MODES} のどれか")
    if run.get("route") not in ROUTE_CHOICES:
        problems.append(f"run.route は {ROUTE_CHOICES} のどれか")
    if not isinstance(run.get("cascade"), bool):
        problems.append("run.cascade（true / false）が無い")
    if mode == "regression":
        if run.get("replay_mode") not in REPLAY_MODES:
            problems.append(f"run.replay_mode は {REPLAY_MODES} のどれか")
        if not isinstance(run.get("runs"), int):
            problems.append("run.runs が無い")
    target = item.get("target", {})
    if not isinstance(target, dict) or set(target) - {"failure_mode", "traces", "exclude_traces"}:
        problems.append("target に書けるのは failure_mode・traces・exclude_traces")
    elif target.get("traces") and not target.get("failure_mode"):
        problems.append("target.traces には failure_mode も書く")

    value = item.get("value")
    if value is not None and not isinstance(value, str):
        problems.append("value は文字列")
    elif isinstance(value, str):
        if value.startswith("turn_analysis.") and "equals" not in item:
            problems.append("turn_analysis の value には equals を書く")
        if value.startswith("calibration.") and (
            mode != "scoring" or value.split(".", 1)[1] not in CALIBRATION_STAGES
        ):
            problems.append(f"calibration は scoring の {CALIBRATION_STAGES} だけ")
    if "read" in item:
        if not isinstance(item["read"], str) or not item["read"]:
            problems.append("read は読む条件の文")
        if "expect" in item:
            problems.append("read（人が読む）と expect（数で判定）は別の項目に分ける")
        return problems
    if value is None:
        problems.append("value（見る値）が無い")
    problems.extend(_expect_problems(item.get("expect")))
    return problems


def _expect_problems(expect: Any) -> list[str]:
    if not isinstance(expect, dict):
        return ["expect（合格の条件）が無い"]
    if set(expect) - {"passes", "of", "baseline", "tolerance"}:
        return ["expect に書けるのは passes・of・baseline・tolerance"]
    if ("passes" in expect) == ("baseline" in expect):
        return ["expect には passes か baseline のどちらか 1 つを書く"]
    if "tolerance" in expect and not (isinstance(expect["tolerance"], int) and expect["tolerance"] >= 0):
        return ["expect.tolerance は 0 以上の整数"]
    if "passes" in expect:
        passes = expect["passes"]
        if passes == "all":
            return ["passes: all は母数が決まっているので of を書かない"] if "of" in expect else []
        if not (isinstance(passes, int) and isinstance(expect.get("of"), int) and 0 <= passes <= expect["of"]):
            return ["expect.passes は all か、of（母数）と組にした整数"]
    return []


@dataclass
class Tally:
    passes: int = 0
    total: int = 0
    by_instance: dict[tuple[str, str], list[int]] = field(default_factory=dict)
    failures: list[tuple[dict[str, Any], dict[str, Any]]] = field(default_factory=list)

    def add(self, record: dict[str, Any], run: dict[str, Any], outcome: str) -> None:
        counts = self.by_instance.setdefault(_record_key(record), [0, 0])
        counts[1] += 1
        self.total += 1
        if outcome == "pass":
            counts[0] += 1
            self.passes += 1
        else:
            self.failures.append((record, run))


@dataclass
class Check:
    status: str
    result: str
    commands: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


def _record_key(record: dict[str, Any]) -> tuple[str, str]:
    return record["failure_mode"], record["source_trace_id"]


def _targeted(report: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    failure_mode = target.get("failure_mode")
    traces = target.get("traces")
    excluded = set(target.get("exclude_traces") or [])
    return [
        record
        for record in report["records"]
        if (failure_mode is None or record["failure_mode"] == failure_mode)
        and (traces is None or record["source_trace_id"] in traces)
        and record["source_trace_id"] not in excluded
    ]


def _assertion(run: dict[str, Any], assertion_id: str) -> dict[str, Any] | None:
    return next((a for a in run["assertions"] if a["assertion_id"] == assertion_id), None)


def run_outcome(item: dict[str, Any], record: dict[str, Any], run: dict[str, Any], mode: str) -> str | None:
    """1 回分の結果。regression は pass 率、scoring は人のラベルとの一致を数える。数えない回は None。"""
    value = item["value"]
    if value == "verdict":
        if mode == "regression":
            return str(run["verdict"])
        if record["human_pass"] is None:
            return None
        return "pass" if (run["verdict"] == "pass") == record["human_pass"] else "fail"
    if value.startswith("turn_analysis."):
        analysis = run.get("turn_analysis") or {}
        return "pass" if analysis.get(value.removeprefix("turn_analysis.")) == item["equals"] else "fail"
    assertion = _assertion(run, value)
    if assertion is None or assertion["judged"] == "na":
        return None
    if mode == "regression":
        return str(assertion["judged"])
    if not assertion["human"]:
        return None
    return "pass" if assertion["judged"] == assertion["human"] else "fail"


def tally(item: dict[str, Any], report: dict[str, Any], keys: set[tuple[str, str]] | None = None) -> Tally:
    result = Tally()
    for record in _targeted(report, item.get("target", {})):
        if keys is not None and _record_key(record) not in keys:
            continue
        for run in record["runs"]:
            outcome = run_outcome(item, record, run, report["meta"]["mode"])
            if outcome is not None:
                result.add(record, run, outcome)
    return result


def _cascade(meta: dict[str, Any]) -> bool:
    return meta["judge"]["confirm"] is not None


def _judging(cascade: bool) -> str:
    return "カスケード" if cascade else "screen だけ（--no-cascade）"


def condition_mismatches(run: dict[str, Any], meta: dict[str, Any]) -> dict[str, str]:
    """プロンプトの値以外の実行条件のずれ。キーは条件の名前。"""
    mismatches: dict[str, str] = {}
    if meta["mode"] != run["mode"]:
        mismatches["mode"] = f"mode が {meta['mode']}（項目は {run['mode']}）"
        return mismatches
    if meta["route"] != run["route"]:
        mismatches["route"] = f"route が {meta['route']}（項目は {run['route']}）"
    if run["mode"] == "regression":
        if meta["replay_mode"] != run["replay_mode"]:
            mismatches["replay_mode"] = f"replay が {meta['replay_mode']}（項目は {run['replay_mode']}）"
        if meta["runs"] != run["runs"]:
            mismatches["runs"] = f"runs が {meta['runs']}（項目は {run['runs']}）"
    if _cascade(meta) != run["cascade"]:
        mismatches["cascade"] = f"採点は {_judging(_cascade(meta))}（項目は {_judging(run['cascade'])}）"
    return mismatches


def fingerprint_mismatches(route: str, meta: dict[str, Any], current: dict[str, str]) -> list[str]:
    keys = {MAP_ROUTE: ["map_prompt_fingerprint"], LEGACY_ROUTE: ["prompt_fingerprint"]}.get(
        route, ["map_prompt_fingerprint", "prompt_fingerprint"]
    )
    return [
        f"{key} が {meta.get(key)}（今のコードは {current[key]}）。今のプロンプトで回したレポートではない"
        for key in keys
        if meta.get(key) != current[key]
    ]


def eval_command(run: dict[str, Any], target: dict[str, Any]) -> str:
    parts = ["uv run python -m evals.eval", f"--mode {run['mode']}", f"--route {run['route']}"]
    if run["mode"] == "regression":
        parts.append(f"--runs {run['runs']}")
        if run["replay_mode"] != "full":
            parts.append(f"--replay-mode {run['replay_mode']}")
        parts.extend(f"--trace {trace}" for trace in target.get("traces") or [])
    if not run["cascade"]:
        parts.append("--no-cascade")
    return " ".join(parts)


def rescore_command(report_path: Path, cascade: bool) -> str:
    return f"uv run python -m evals.eval --rescore-report {report_path}" + ("" if cascade else " --no-cascade")


def _coverage_reasons(item: dict[str, Any], report: dict[str, Any]) -> list[str]:
    target = item.get("target", {})
    if target.get("traces"):
        present = {_record_key(r) for r in report["records"]}
        missing = [t for t in target["traces"] if (target["failure_mode"], t) not in present]
        return [f"レポートに無い instance: {', '.join(missing)}"] if missing else []
    if report["meta"].get("traces") is not None:
        return ["レポートが --trace で一部の instance だけを回したもの（項目は全件を見る）"]
    if not _targeted(report, target):
        return ["レポートに該当する instance が無い"]
    return []


def _describe_run(record: dict[str, Any], run: dict[str, Any], item: dict[str, Any]) -> str:
    lines = [f"- `{record['failure_mode']}/{record['source_trace_id']}` run {run['run_index']}（{run['verdict']}）"]
    lines.append(f"  - 応答: {run['output']}")
    value = item.get("value")
    if value and (assertion := _assertion(run, value)) is not None:
        lines.append(f"  - {value}（{assertion['judged']}・{assertion['decided_by']}）: {assertion['detail']}")
    if value and value.startswith("turn_analysis."):
        lines.append(f"  - turn_analysis: {run.get('turn_analysis')}")
    return "\n".join(lines)


def _load_report(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def check_item(
    item: dict[str, Any],
    report: dict[str, Any],
    report_path: Path,
    *,
    current: dict[str, str],
    evals_dir: Path = EVALS_DIR,
) -> Check:
    run, target, meta = item["run"], item.get("target", {}), report["meta"]
    mismatches = condition_mismatches(run, meta)
    fingerprints = fingerprint_mismatches(run["route"], meta, current)
    coverage = _coverage_reasons(item, report)
    if mismatches or fingerprints or coverage:
        reasons = [*mismatches.values(), *fingerprints, *coverage]
        only_cascade = set(mismatches) == {"cascade"} and not fingerprints and not coverage
        command = (
            rescore_command(report_path, run["cascade"])
            if only_cascade and run["mode"] == "regression"
            else eval_command(run, target)
        )
        return Check(NOT_COVERED, "; ".join(reasons), commands=[command])

    if "read" in item:
        records = _targeted(report, target)
        details = [_describe_run(record, r, item) for record in records for r in record["runs"]]
        runs = sum(len(record["runs"]) for record in records)
        return Check(TO_READ, f"{runs} 回分の応答を読む: {item['read']}", details=details)

    value = item["value"]
    if value.startswith("calibration."):
        gate = report["agreement"]["calibration"][value.removeprefix("calibration.")]
        status = PASSED if gate["passed"] else FAILED
        return Check(status, f"{value}: {'PASS' if gate['passed'] else 'FAIL ' + '; '.join(gate['failures'])}")

    expect = item["expect"]
    if "baseline" in expect:
        return _check_against_baseline(item, report, evals_dir / expect["baseline"])

    observed = tally(item, report)
    if expect["passes"] == "all":
        reference, total, tolerance = observed.total, observed.total, expect.get("tolerance", 0)
    else:
        reference, total, tolerance = expect["passes"], expect["of"], expect.get("tolerance", DEFAULT_TOLERANCE)
        if observed.total != total:
            reason = f"母数が {observed.total}（項目は {total}）。instance か runs の数が違う"
            return Check(NOT_COVERED, reason, commands=[eval_command(run, target)])
    return _numeric_check(item, observed, reference, tolerance, total, observed.failures)


def _numeric_check(
    item: dict[str, Any],
    observed: Tally,
    reference: int,
    tolerance: int,
    total: int,
    failures: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    baseline_label: str = "",
) -> Check:
    floor = reference - tolerance
    passed = observed.passes >= floor
    result = (
        f"{item['value']} {observed.passes}/{observed.total}"
        f"（基準 {reference}/{total}{baseline_label}・許容 {tolerance} 件 → {floor} 以上で合格）"
    )
    details = [] if passed else [_describe_run(record, run, item) for record, run in failures]
    return Check(PASSED if passed else FAILED, result, details=details)


def _check_against_baseline(item: dict[str, Any], report: dict[str, Any], baseline_path: Path) -> Check:
    run = item["run"]
    baseline = _load_report(baseline_path)
    if baseline is None:
        return Check(NOT_COVERED, f"比べるレポート {baseline_path.name} が無い")
    mismatches = condition_mismatches(run, baseline["meta"])
    if mismatches:
        reasons = [f"比べるレポートの{text}" for text in mismatches.values()]
        command = (
            rescore_command(baseline_path, run["cascade"])
            if set(mismatches) == {"cascade"} and run["mode"] == "regression"
            else eval_command(run, item.get("target", {}))
        )
        return Check(NOT_COVERED, "; ".join(reasons), commands=[command])

    shared = {_record_key(r) for r in _targeted(report, item.get("target", {}))} & {
        _record_key(r) for r in _targeted(baseline, item.get("target", {}))
    }
    observed = tally(item, report, shared)
    reference = tally(item, baseline, shared)
    tolerance = item["expect"].get("tolerance", DEFAULT_TOLERANCE)
    dropped = {
        key for key, (passes, _) in observed.by_instance.items() if passes < reference.by_instance.get(key, [0, 0])[0]
    }
    failures = [(record, r) for record, r in observed.failures if _record_key(record) in dropped]
    return _numeric_check(
        item,
        observed,
        reference.passes,
        tolerance,
        reference.total,
        failures,
        baseline_label=f"・{baseline_path.name}",
    )


def verify(
    report_path: Path,
    *,
    pending_dir: Path = PENDING_DIR,
    current: dict[str, str] | None = None,
    today: date | None = None,
    write: bool = True,
    recheck: bool = False,
) -> list[tuple[dict[str, Any], list[tuple[dict[str, Any], Check]]]]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    current = current or current_fingerprints()
    today = today or date.today()
    results: list[tuple[dict[str, Any], list[tuple[dict[str, Any], Check]]]] = []
    for path, document in load_pending(pending_dir):
        if problems := document_problems(path, document):
            raise SystemExit("\n".join(problems))
        checked: list[tuple[dict[str, Any], Check]] = []
        for item in document["items"]:
            if item["status"] in SETTLED and (not recheck or "read" in item):
                continue
            check = check_item(item, report, report_path, current=current, evals_dir=pending_dir.parent)
            checked.append((item, check))
            if item["status"] == TO_READ and check.status == NOT_COVERED:
                continue
            item.update(status=check.status, checked_on=today, report=report_path.name, result=check.result)
        if write and checked:
            save_pending(path, document)
        results.append((document, checked))
    return results


def all_settled(document: dict[str, Any]) -> bool:
    return all(item["status"] in SETTLED for item in document["items"])


def markdown_summary(document: dict[str, Any]) -> str:
    lines = [
        f"## #{document['issue']} {document['summary']} の eval の確認",
        "",
        "| 項目 | 状態 | 日付 | レポート | 結果 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in document["items"]:
        lines.append(
            f"| `{item['id']}` | {item['status']} | {item.get('checked_on') or '-'} | "
            f"{item.get('report') or '-'} | {str(item.get('result') or '-').replace('|', '\\|')} |"
        )
    return "\n".join(lines)


def print_listing(pending_dir: Path = PENDING_DIR) -> None:
    for path, document in load_pending(pending_dir):
        print(f"#{document['issue']} {document['summary']}（{path.relative_to(pending_dir.parent)}）")
        for item in document["items"]:
            run = item["run"]
            print(f"  [{item['status']}] {item['id']}  {run['mode']} route={run['route']}  {item.get('result') or ''}")


def print_results(results: list[tuple[dict[str, Any], list[tuple[dict[str, Any], Check]]]]) -> None:
    for document, checked in results:
        if not checked:
            continue
        print("=" * 100)
        print(f"#{document['issue']} {document['summary']}")
        for item, check in checked:
            print(f"\n[{check.status}] {item['id']}: {check.result}")
            for command in check.commands:
                print(f"  そろえるコマンド: {command}")
            for detail in check.details:
                print(detail)
        print("\n" + markdown_summary(document))
        if all_settled(document):
            issue = document["issue"]
            print(f"\n全項目が済んだ。上の要約を #{issue} にコメントし、pending/{issue}.yaml を消す")


def main() -> None:
    parser = argparse.ArgumentParser(prog="evals.verify", description="確認待ちの項目を eval のレポートと照合する")
    parser.add_argument("report", type=Path, nargs="?", help="照合する eval のレポート（JSON）")
    parser.add_argument("--list", action="store_true", help="確認待ちの項目を一覧して終了する")
    parser.add_argument("--dry-run", action="store_true", help="結果を項目のファイルに書き戻さない")
    parser.add_argument("--recheck", action="store_true", help="合格・不合格の済んだ項目も照合し直す")
    args = parser.parse_args()
    if args.list:
        print_listing()
        return
    if args.report is None:
        parser.error("照合するレポートを渡すか、--list を付ける")
    print_results(verify(args.report, write=not args.dry_run, recheck=args.recheck))


if __name__ == "__main__":
    main()
