import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from langchain_core.language_models import BaseChatModel

from evals.checkpoint import CheckpointStore, dataset_content_hash, sha256_bytes
from evals.checks import run_check
from evals.dataset import (
    ALL_ROUTES,
    GOLDEN_DIR,
    NOT_APPLICABLE,
    RUBRIC_DIR,
    SourceTrace,
    get_source_trace,
    load_golden_records,
    load_source_records,
    route_blocker,
    validate_check_fingerprints,
    validate_human_verdicts,
)
from evals.judge import JudgeUsage, judge_by_llm, judge_model_name, should_escalate, to_verdict
from evals.replay import Generation, generate_output, replay_blocker
from evals.retry import QuotaExhausted
from evals.rubric import FAILURE_MODE_SCOPE
from graph.llm import RESPONSE_MODELS
from graph.prompts.map_question import MAP_PROMPT_FINGERPRINT
from graph.prompts.question import PROMPT_FINGERPRINT, PROMPT_VERSION

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssertionOutcome:
    assertion_id: str
    assertion_type: str
    polarity: str
    holds: bool | None
    verdict: str
    human_verdict: str
    detail: str
    decided_by: str = "check"
    screen_holds: bool | None = None
    screen_detail: str = ""
    scope: str = FAILURE_MODE_SCOPE

    @property
    def applicable(self) -> bool:
        return self.verdict != NOT_APPLICABLE

    @property
    def agrees(self) -> bool:
        return self.applicable and bool(self.human_verdict) and self.verdict == self.human_verdict

    @property
    def screen_verdict(self) -> str:
        """screen 単体の verdict。judge 以外（deterministic / na）は final と同じ。"""
        if self.assertion_type != "judge" or self.screen_holds is None:
            return self.verdict
        return to_verdict(self.polarity, self.screen_holds)

    @property
    def escalated(self) -> bool:
        return self.decided_by == "confirm"


@dataclass
class RunResult:
    run_index: int
    output: str
    outcomes: list[AssertionOutcome]
    generation: Generation | None = None

    @property
    def verdict(self) -> str:
        return aggregate_verdict(self.outcomes)


@dataclass
class InstanceResult:
    failure_mode: str
    source_trace_id: str
    human_pass: bool | None
    runs: list[RunResult] = field(default_factory=list)


def aggregate_verdict(outcomes: list[AssertionOutcome]) -> str:
    """must が満たされ must_not が現れていなければ pass。適用外（na）は中立。"""
    scored = [o for o in outcomes if o.applicable]
    return "pass" if all(o.verdict == "pass" for o in scored) else "fail"


async def evaluate_assertion(
    assertion: dict[str, Any],
    trace: SourceTrace,
    output: str,
    human_verdicts: dict[str, str],
    judge: BaseChatModel,
    *,
    compare_to_human: bool,
    confirm_judge: BaseChatModel | None = None,
    usage: JudgeUsage | None = None,
) -> AssertionOutcome:
    declared = human_verdicts[assertion["id"]]
    human_verdict = declared if compare_to_human else ""

    if declared == NOT_APPLICABLE:
        return AssertionOutcome(
            assertion_id=assertion["id"],
            assertion_type=assertion["type"],
            polarity=assertion["polarity"],
            holds=None,
            verdict=NOT_APPLICABLE,
            human_verdict=human_verdict,
            detail=f"applies_when: {assertion.get('applies_when', '').strip()}",
            decided_by=NOT_APPLICABLE,
            scope=assertion.get("scope", FAILURE_MODE_SCOPE),
        )

    screen_holds: bool | None = None
    screen_detail = ""
    if assertion["type"] == "judge":
        screened = await judge_by_llm(assertion, trace, output, judge, usage)
        screen_holds, screen_detail = screened.holds, screened.reason
        holds, detail, decided_by = screen_holds, screen_detail, "screen"
        if confirm_judge is not None and should_escalate(assertion["polarity"], screen_holds):
            confirmed = await judge_by_llm(assertion, trace, output, confirm_judge, usage)
            holds, detail, decided_by = confirmed.holds, confirmed.reason, "confirm"
    elif assertion["type"] == "deterministic":
        outcome = run_check(assertion["check"], output, trace.input["conversation_history"])
        holds, detail, decided_by = outcome.holds, outcome.detail, "check"
    else:
        raise ValueError(f"unknown assertion type: {assertion['type']!r} (expected 'judge' or 'deterministic')")

    return AssertionOutcome(
        assertion_id=assertion["id"],
        assertion_type=assertion["type"],
        polarity=assertion["polarity"],
        holds=holds,
        verdict=to_verdict(assertion["polarity"], holds),
        human_verdict=human_verdict,
        detail=detail,
        decided_by=decided_by,
        screen_holds=screen_holds,
        screen_detail=screen_detail,
        scope=assertion.get("scope", FAILURE_MODE_SCOPE),
    )


async def evaluate_output(
    record: dict[str, Any],
    instance: dict[str, Any],
    trace: SourceTrace,
    output: str,
    judge: BaseChatModel,
    *,
    compare_to_human: bool,
    confirm_judge: BaseChatModel | None = None,
    usage: JudgeUsage | None = None,
) -> list[AssertionOutcome]:
    return list(
        await asyncio.gather(
            *(
                evaluate_assertion(
                    assertion,
                    trace,
                    output,
                    instance["human_verdicts"],
                    judge,
                    compare_to_human=compare_to_human,
                    confirm_judge=confirm_judge,
                    usage=usage,
                )
                for assertion in record["assertions"]
            )
        )
    )


async def _checkpointed_generation(
    trace: SourceTrace,
    replay_mode: str,
    checkpoint: CheckpointStore,
    failure_mode: str,
    source_trace_id: str,
    run_index: int,
) -> Generation:
    cached = checkpoint.load_generation(failure_mode, source_trace_id, run_index)
    if cached is not None:
        return Generation.from_checkpoint(cached)
    generation = await generate_output(trace, replay_mode)
    checkpoint.save_generation(failure_mode, source_trace_id, run_index, asdict(generation))
    return generation


async def _checkpointed_outcomes(
    record: dict[str, Any],
    instance: dict[str, Any],
    trace: SourceTrace,
    output: str,
    judge: BaseChatModel,
    *,
    compare_to_human: bool,
    confirm_judge: BaseChatModel | None,
    usage: JudgeUsage | None,
    checkpoint: CheckpointStore,
    failure_mode: str,
    source_trace_id: str,
    run_index: int,
) -> list[AssertionOutcome]:
    generation_sha256 = sha256_bytes(output.encode("utf-8"))
    cached = checkpoint.load_score(failure_mode, source_trace_id, run_index)
    if cached is not None and cached.get("generation_sha256") == generation_sha256:
        if usage is not None:
            usage.merge(cached.get("judge_usage", {}))
        return [AssertionOutcome(**outcome) for outcome in cached["assertions"]]

    run_usage = JudgeUsage()
    outcomes = await evaluate_output(
        record,
        instance,
        trace,
        output,
        judge,
        compare_to_human=compare_to_human,
        confirm_judge=confirm_judge,
        usage=run_usage,
    )
    checkpoint.save_score(
        failure_mode,
        source_trace_id,
        run_index,
        {
            "generation_sha256": generation_sha256,
            "assertions": [asdict(outcome) for outcome in outcomes],
            "judge_usage": run_usage.to_report(),
        },
    )
    if usage is not None:
        usage.merge(run_usage.to_report())
    return outcomes


async def evaluate_instance(
    record: dict[str, Any],
    instance: dict[str, Any],
    trace: SourceTrace,
    judge: BaseChatModel,
    *,
    mode: str,
    runs: int,
    confirm_judge: BaseChatModel | None = None,
    usage: JudgeUsage | None = None,
    replay_mode: str = "full",
    checkpoint: CheckpointStore | None = None,
    errors: list[str] | None = None,
) -> InstanceResult:
    """golden の 1 instance を評価する。

    run 単位で例外を吸収し、その run だけを結果から除いて次の run へ進む（`errors` に記録）。
    `QuotaExhausted` だけは吸収せずそのまま上げ、`run()` 側で実行全体を止める。
    """
    failure_mode = record["failure_mode"]
    source_trace_id = instance["source_trace_id"]
    label = f"{failure_mode}/{source_trace_id}"
    result = InstanceResult(
        failure_mode=failure_mode, source_trace_id=source_trace_id, human_pass=instance.get("pass")
    )
    compare_to_human = mode == "scoring"
    for run_index in range(1, (runs if mode == "regression" else 1) + 1):
        try:
            if mode == "regression":
                generation = (
                    await _checkpointed_generation(
                        trace, replay_mode, checkpoint, failure_mode, source_trace_id, run_index
                    )
                    if checkpoint is not None
                    else await generate_output(trace, replay_mode)
                )
                output = generation.output
            else:
                generation, output = None, trace.observed_output
            outcomes = (
                await _checkpointed_outcomes(
                    record,
                    instance,
                    trace,
                    output,
                    judge,
                    compare_to_human=compare_to_human,
                    confirm_judge=confirm_judge,
                    usage=usage,
                    checkpoint=checkpoint,
                    failure_mode=failure_mode,
                    source_trace_id=source_trace_id,
                    run_index=run_index,
                )
                if checkpoint is not None
                else await evaluate_output(
                    record,
                    instance,
                    trace,
                    output,
                    judge,
                    compare_to_human=compare_to_human,
                    confirm_judge=confirm_judge,
                    usage=usage,
                )
            )
        except QuotaExhausted:
            raise
        except Exception as exc:
            logger.exception("run failed: %s run=%d", label, run_index)
            if errors is not None:
                errors.append(f"{label} run={run_index}: {type(exc).__name__}: {exc}")
            continue
        result.runs.append(RunResult(run_index=run_index, output=output, outcomes=outcomes, generation=generation))
    return result


def print_instance(result: InstanceResult) -> None:
    print("=" * 100)
    print(f"failure_mode={result.failure_mode}  source_trace_id={result.source_trace_id}")
    print("-" * 100)
    for run in result.runs:
        if len(result.runs) > 1:
            analysis = run.generation.turn_analysis if run.generation else None
            print(f"[run {run.run_index}] verdict={run.verdict}  turn_analysis={analysis}")
            print(f"          {run.output[:120]}...")
        for outcome in run.outcomes:
            if not outcome.applicable:
                mark = "-- "
            elif not outcome.human_verdict:
                mark = "   "
            else:
                mark = "OK " if outcome.agrees else "NG "
            human = f" human={outcome.human_verdict}" if outcome.human_verdict else ""
            print(
                f"{mark}{outcome.assertion_id}  {outcome.assertion_type:<13} {outcome.polarity:<8} "
                f"holds={str(outcome.holds):<5} judged={outcome.verdict:<4}{human}"
            )
            print(f"      {outcome.detail}")
        print()


def build_manifest(
    mode: str,
    runs: int,
    replay_mode: str,
    judge: BaseChatModel,
    confirm_judge: BaseChatModel | None,
    fingerprints: dict[str, str],
    route: str = ALL_ROUTES,
    traces: frozenset[str] | None = None,
) -> dict[str, Any]:
    """checkpoint の実行条件。いずれかが変われば再開を拒否する（`CheckpointStore.ensure_manifest`）。"""
    return {
        "mode": mode,
        "runs": runs,
        "replay_mode": replay_mode,
        "route": route,
        "traces": sorted(traces) if traces is not None else None,
        "judge_screen": judge_model_name(judge),
        "judge_confirm": judge_model_name(confirm_judge) if confirm_judge is not None else None,
        "model": RESPONSE_MODELS["learning-dialogue"].model,
        "temperature": RESPONSE_MODELS["learning-dialogue"].temperature,
        "prompt_version": PROMPT_VERSION,
        "prompt_fingerprint": PROMPT_FINGERPRINT,
        "map_prompt_fingerprint": MAP_PROMPT_FINGERPRINT,
        "check_fingerprints": fingerprints,
        "dataset_content_sha256": dataset_content_hash(GOLDEN_DIR, RUBRIC_DIR),
    }


async def run(
    mode: str,
    runs: int,
    judge: BaseChatModel,
    *,
    confirm_judge: BaseChatModel | None = None,
    replay_mode: str = "full",
    checkpoint: CheckpointStore | None = None,
    route: str = ALL_ROUTES,
    traces: frozenset[str] | None = None,
) -> tuple[list[InstanceResult], list[str], dict[str, str], JudgeUsage, list[dict[str, str]]]:
    fingerprints = validate_check_fingerprints()
    records = list(load_golden_records())
    validate_human_verdicts(records)
    sources = load_source_records()
    usage = JudgeUsage()
    if checkpoint is not None:
        checkpoint.ensure_manifest(
            build_manifest(mode, runs, replay_mode, judge, confirm_judge, fingerprints, route=route, traces=traces)
        )

    results: list[InstanceResult] = []
    errors: list[str] = []
    skipped: list[dict[str, str]] = []
    for record in records:
        seen_inputs: set[str] = set()
        for instance in record["instances"]:
            if traces is not None and instance["source_trace_id"] not in traces:
                continue
            label = f"{record['failure_mode']}/{instance['source_trace_id']}"
            try:
                trace = get_source_trace(instance["source_trace_id"], sources)
            except Exception as exc:
                logger.exception("instance failed: %s", label)
                errors.append(f"{label}: {type(exc).__name__}: {exc}")
                continue

            blocker = route_blocker(trace, route)
            if blocker is None and mode == "regression":
                blocker = replay_blocker(trace, replay_mode)
            if blocker is not None:
                print(f"skip {label}: {blocker}")
                skipped.append(
                    {
                        "failure_mode": record["failure_mode"],
                        "source_trace_id": instance["source_trace_id"],
                        "reason": blocker,
                    }
                )
                continue
            if mode == "regression":
                fingerprint = json.dumps(trace.input, ensure_ascii=False, sort_keys=True)
                if fingerprint in seen_inputs:
                    print(f"skip {label}: 同一 input の instance を再生成済み")
                    continue
                seen_inputs.add(fingerprint)

            try:
                result = await evaluate_instance(
                    record,
                    instance,
                    trace,
                    judge,
                    mode=mode,
                    runs=runs,
                    confirm_judge=confirm_judge,
                    usage=usage,
                    replay_mode=replay_mode,
                    checkpoint=checkpoint,
                    errors=errors,
                )
            except QuotaExhausted as exc:
                errors.append(f"{label}: quota exhausted, stopping remaining instances: {exc}")
                logger.error("quota exhausted, stopping regression early at %s", label)
                return results, errors, fingerprints, usage, skipped
            except Exception as exc:
                logger.exception("instance failed: %s", label)
                errors.append(f"{label}: {type(exc).__name__}: {exc}")
                continue
            print_instance(result)
            results.append(result)
    return results, errors, fingerprints, usage, skipped
