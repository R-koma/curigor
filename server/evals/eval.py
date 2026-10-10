import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

from evals.checkpoint import CheckpointStore, ManifestMismatch
from evals.dataset import ALL_ROUTES, ROUTE_CHOICES, load_golden_records, load_source_records, unannotated_ids
from evals.emit import emit_jsonl
from evals.golden_yaml import dump_copy_block
from evals.judge import (
    DEFAULT_CONFIRM_MODEL,
    JudgeEffort,
    judge_model_name,
    resolve_confirm_judge,
    resolve_judge,
    set_judge_cache,
)
from evals.judge_cache import JudgeCache
from evals.report import build_report, print_summary
from evals.runner import run
from graph.llm import RESPONSE_MODELS
from graph.prompts.map_question import MAP_PROMPT_FINGERPRINT
from graph.prompts.question import PROMPT_FINGERPRINT, PROMPT_VERSION

_REPORTS_DIR = Path(__file__).parent / "reports"
_JUDGE_CACHE_DIR = Path(__file__).parent / ".judge_cache"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="evals.eval", description="golden レコードに対する eval ランナー")
    parser.add_argument("--mode", choices=("scoring", "regression"), default="scoring")
    parser.add_argument("--runs", type=int, default=3, help="regression の1インスタンスあたり生成回数")
    parser.add_argument("--out", type=Path, default=None, help="レポートの出力先（既定は evals/reports/）")
    parser.add_argument("--emit-jsonl", type=Path, default=None, help="regression の生成を正本 jsonl へ追記する")
    parser.add_argument("--emit-instance", default=None, help="trace id を指定して golden 用の写しを出力する")
    parser.add_argument(
        "--list-unannotated", action="store_true", help="正本 jsonl の未 annotate レコードを一覧して終了する"
    )
    parser.add_argument(
        "--replay-mode",
        choices=("full", "pinned"),
        default="full",
        help="regression の再実行方法。full=事前分析込み（分析の揺れも入る）/ "
        "pinned=保存済みの turn_decision を注入して応答生成だけ再実行（プロンプト改訂の効果を分離）",
    )
    parser.add_argument(
        "--route",
        choices=ROUTE_CHOICES,
        default=ALL_ROUTES,
        help="再生・採点する instance の経路。map=地図に沿った経路 / legacy=旧経路（meta.route なし）/ all=両方",
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        help="screen（1段目）に使う Anthropic モデル（既定は graph.llm の llm_judge）。criterion の曖昧さは"
        "モデル間の判定の割れとして現れるため、複数モデルで確認する",
    )
    parser.add_argument(
        "--judge-effort",
        choices=get_args(JudgeEffort),
        default=None,
        help="screen（1段目）の effort。effort を受け付けるモデル（Haiku 5.5 など）を --judge-model で"
        "指定したときだけ付けられる",
    )
    parser.add_argument(
        "--confirm-judge-model",
        default=None,
        help=f"confirm（2段目）に使う Anthropic モデル（既定は {DEFAULT_CONFIRM_MODEL}）。"
        "screen が fail と判定した judge assertion だけ確認に回す（--no-cascade で無効化）",
    )
    parser.add_argument(
        "--no-cascade",
        action="store_true",
        help="confirm 段を無効化し、screen 単体の判定を最終値にする（従来の単一 judge 相当）",
    )
    parser.add_argument(
        "--trace",
        action="append",
        default=None,
        help="golden の source_trace_id を指定し、その instance だけを再生・採点する（複数回指定できる）。"
        "プロンプトを直している途中の安い確認用。他の項目が下がっていないかは、最後に全件で確かめる",
    )
    parser.add_argument(
        "--no-judge-cache",
        action="store_true",
        help="保存済みの judge の判定を読まずに採点する（同じ入力での判定の揺れを見るとき）。結果は保存し直す",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="scoring モードで最終判定の校正ゲート（TPR/TNR ≥ 90%% かつ正例レコード全件 pass）が"
        "不合格のとき exit code 1 で終了する",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=None,
        help="生成・採点の保存先。既定は reports/ 配下に実行ごとに自動生成する。既存のディレクトリを"
        "指定すると、保存済みの run は作り直さず未完了分だけ実行する（実行条件が前回と違えば拒否する）",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    if args.emit_instance:
        print(dump_copy_block(load_source_records()[args.emit_instance]), end="")
        return

    if args.list_unannotated:
        for trace_id in unannotated_ids(load_source_records()):
            print(trace_id)
        return

    if args.trace and args.strict:
        raise SystemExit("--trace は一部の instance しか採点しないので、--strict の校正ゲートと併用できない")
    traces = frozenset(args.trace) if args.trace else None
    if traces is not None:
        known = {instance["source_trace_id"] for record in load_golden_records() for instance in record["instances"]}
        if unknown := traces - known:
            raise SystemExit(f"golden に無い trace id: {sorted(unknown)}")
    try:
        judge = resolve_judge(args.judge_model, args.judge_effort)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    set_judge_cache(JudgeCache(_JUDGE_CACHE_DIR, read=not args.no_judge_cache))
    confirm_judge = resolve_confirm_judge(args.confirm_judge_model, cascade=not args.no_cascade)
    response_model = RESPONSE_MODELS["learning-dialogue"]
    print(f"mode={args.mode} model={response_model.model} temperature={response_model.temperature}")
    confirm_label = judge_model_name(confirm_judge) if confirm_judge is not None else "none"
    print(
        f"judge(screen)={judge_model_name(judge)} judge(confirm)={confirm_label} "
        f"prompt_version={PROMPT_VERSION} prompt_fingerprint={PROMPT_FINGERPRINT} "
        f"map_prompt_fingerprint={MAP_PROMPT_FINGERPRINT} route={args.route}\n"
    )

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    checkpoint_dir = args.checkpoint_dir or _REPORTS_DIR / f"{timestamp}-{args.mode}-checkpoint"
    checkpoint = CheckpointStore(checkpoint_dir)
    print(f"checkpoint: {checkpoint_dir}\n")

    try:
        results, errors, fingerprints, usage, skipped = await run(
            args.mode,
            args.runs,
            judge,
            confirm_judge=confirm_judge,
            replay_mode=args.replay_mode,
            checkpoint=checkpoint,
            route=args.route,
            traces=traces,
        )
    except ManifestMismatch as exc:
        raise SystemExit(str(exc)) from None
    report = build_report(
        results,
        errors,
        mode=args.mode,
        runs=args.runs,
        fingerprints=fingerprints,
        judge=judge,
        confirm_judge=confirm_judge,
        usage=usage,
        skipped=skipped,
        replay_mode=args.replay_mode,
        route=args.route,
        traces=traces,
    )
    print_summary(report)

    out = args.out or _REPORTS_DIR / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{args.mode}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nreport: {out}")

    if args.emit_jsonl:
        written = emit_jsonl(args.emit_jsonl, results, load_source_records())
        print(f"emitted {len(written)} record(s) to {args.emit_jsonl}")

    if args.strict and args.mode == "scoring" and not report["agreement"]["calibration"]["final"]["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
