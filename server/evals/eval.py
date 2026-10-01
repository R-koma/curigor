import argparse
import asyncio
import json
import logging
import math
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self
from uuid import uuid4

import yaml
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field

from evals.checkpoint import CheckpointStore, ManifestMismatch, dataset_content_hash, sha256_bytes
from evals.checks import check_fingerprint, run_check
from evals.golden_yaml import dump_copy_block
from evals.rubric import FAILURE_MODE_SCOPE, RUBRIC_SCOPE, load_rubric, merge_assertions
from evals.tools.capture import CAPTURED_BY, MAP_ROUTE
from graph.llm import llm, llm_judge
from graph.nodes._map_dialogue import MapTurnPlan, respond_map
from graph.nodes.learning_dialogue import TurnPlan, learning_dialogue, respond
from graph.output_schemas import DialogueTurnAnalysis, MapDialogueTurnAnalysis
from graph.prompts.map_question import MAP_PROMPT_FINGERPRINT
from graph.prompts.question import PROMPT_FINGERPRINT, PROMPT_VERSION
from graph.state import LearningState

logger = logging.getLogger(__name__)

_GOLDEN_DIR = Path(__file__).parent / "datasets" / "golden"
_RUBRIC_DIR = Path(__file__).parent / "datasets" / "rubric"
_JSONL_PATH = Path(__file__).parent / "datasets" / "generate_questions.jsonl"
_REPORTS_DIR = Path(__file__).parent / "reports"

_JUDGE_MAX_ATTEMPTS = 3
_GENERATE_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 1.0
_EVAL_USER_ID = "eval-regression"
_NOT_APPLICABLE = "na"
_VALID_VERDICTS = frozenset({"pass", "fail", _NOT_APPLICABLE})

# openai / anthropic の両 SDK が同名で持つ、再試行してよい一時的なエラーの型名
_TRANSIENT_ERROR_TYPES = frozenset({"APIConnectionError", "APITimeoutError", "RateLimitError", "InternalServerError"})
# エラーメッセージに現れる課金枯渇の目印。再試行しても直らないので実行全体を止める
_QUOTA_EXHAUSTED_MARKERS = ("insufficient_quota", "credit balance is too low", "exceeded your current quota")


class QuotaExhausted(RuntimeError):
    """API の課金上限・クレジット枯渇。再試行では直らないため、呼び出し元は実行全体を止める。"""


def _is_transient(exc: Exception) -> bool:
    return type(exc).__name__ in _TRANSIENT_ERROR_TYPES


def _is_quota_exhausted(exc: Exception) -> bool:
    text = str(exc)
    return any(marker in text for marker in _QUOTA_EXHAUSTED_MARKERS)


JUDGE_PROMPT = """\
## 役割
あなたは、学習支援 AI の応答を評価する専門家です。

## 評価対象
学習者と AI の会話履歴、および直近の AI 応答が与えられます。
判定するのは「直近の AI 応答」だけです。

## 学習トピック
{topic}

## 会話履歴
{conversation}

## 直近の AI 応答（判定対象）
{observed_output}

## 判定基準
次の記述が、直近の AI 応答について成り立っているかを判定してください。

{criterion}

## 注意事項
- 記述が成り立つなら holds=true、成り立たないなら holds=false を返してください。
- 応答の良し悪しは判断しません。記述が事実として当てはまるかだけを見ます。
- reason を先に書き、その reason に基づいて holds を決めてください。
- reason は 1〜2 文で、応答のどの箇所を根拠にしたかを引用してください。
- reason と holds は必ず両方とも出力してください。
"""

JUDGE_RETRY_SUFFIX = """
## 前回の出力の不備
前回の応答は構造化出力として解釈できませんでした:

{error}

reason と holds の両方を必ず含めてください。holds は true か false のどちらかです。
reason だけを返してはいけません。
"""


class JudgeResult(BaseModel):
    reason: str = Field(..., description="判定の根拠。1〜2文で、応答のどの箇所を根拠にしたかを引用する")
    holds: bool = Field(..., description="判定基準の記述が、判定対象の応答について成り立っているか")


@dataclass(frozen=True)
class SourceTrace:
    trace_id: str
    turn: int
    meta: dict[str, Any]
    input: dict[str, Any]
    observed_output: str
    turn_decision: dict[str, Any] | None = None
    has_turn_decision: bool = False


LEGACY_ROUTE = "legacy"
ALL_ROUTES = "all"
ROUTE_CHOICES = (ALL_ROUTES, MAP_ROUTE, LEGACY_ROUTE)


def trace_route(trace: SourceTrace) -> str:
    return MAP_ROUTE if trace.meta.get("route") == MAP_ROUTE else LEGACY_ROUTE


def route_blocker(trace: SourceTrace, route: str) -> str | None:
    instance_route = trace_route(trace)
    if route in (ALL_ROUTES, instance_route):
        return None
    return f"--route {route} の対象外（{instance_route} の経路）"


@dataclass(frozen=True)
class Generation:
    output: str
    turn_analysis: dict[str, Any] | None
    covered_aspects: list[dict[str, Any]]
    turn_count: int
    map_covered: list[dict[str, Any]] = field(default_factory=list)
    depth_map: dict[str, Any] | None = None

    @classmethod
    def from_checkpoint(cls, cached: dict[str, Any]) -> Self:
        return cls(
            output=cached["output"],
            turn_analysis=cached["turn_analysis"],
            covered_aspects=cached["covered_aspects"],
            turn_count=cached["turn_count"],
            map_covered=cached.get("map_covered") or [],
            depth_map=cached.get("depth_map"),
        )

    def turn_decision(self) -> dict[str, Any] | None:
        """そのターンがプロンプトへ注入した決定値（capture の `turn_decision` と同じ形）。"""
        if not self.turn_analysis:
            return None
        if self.depth_map is not None:
            return {**self.turn_analysis, "depth_map": self.depth_map, "map_covered": self.map_covered}
        return {**self.turn_analysis, "covered_aspects": self.covered_aspects}


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
        return self.verdict != _NOT_APPLICABLE

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


_TEMPERATURE_UNSUPPORTED: frozenset[str] = frozenset({"claude-opus-5", "claude-opus-5-5", "claude-sonnet-5"})


def resolve_judge(model: str | None) -> BaseChatModel:
    """`--judge-model` が指定されていればその Anthropic モデルを、無ければ既定の judge を返す。"""
    if model is None:
        return llm_judge
    if model in _TEMPERATURE_UNSUPPORTED:
        return ChatAnthropic(model=model)
    return ChatAnthropic(model=model, temperature=0)


_DEFAULT_CONFIRM_MODEL = "claude-opus-5"


def resolve_confirm_judge(model: str | None, *, cascade: bool) -> BaseChatModel | None:
    """`--no-cascade` なら None（従来の単一 judge）。既定の confirm モデルは claude-opus-5。

    claude-opus-5-5 は `--confirm-judge-model` で明示すれば使えるが、既定には採用していない。
    scoring で final TPR が 93%→82%（閾値 90%）に落ちる劣化を 2026-09-26 に確認した
    （screen の正しい fail 判定を pass へ誤って覆す）。
    """
    if not cascade:
        return None
    return resolve_judge(model if model is not None else _DEFAULT_CONFIRM_MODEL)


def judge_model_name(judge: BaseChatModel) -> str:
    name = getattr(judge, "model", None) or getattr(judge, "model_name", None)
    return str(name) if name else type(judge).__name__


_JUDGE_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-5": (5.0, 25.0),
}


def _price_for(model: str) -> tuple[float, float] | None:
    for prefix, price in _JUDGE_PRICE_PER_MTOK.items():
        if model.startswith(prefix):
            return price
    return None


@dataclass
class JudgeUsage:
    """judge 呼び出しのトークン使用量をモデル別に集計する（regression のコスト実測用）。"""

    per_model: dict[str, dict[str, int]] = field(default_factory=dict)

    def record(self, model: str, raw: BaseMessage | None) -> None:
        stats = self.per_model.setdefault(model, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
        stats["calls"] += 1
        usage = getattr(raw, "usage_metadata", None) if raw is not None else None
        if usage:
            stats["input_tokens"] += usage.get("input_tokens") or 0
            stats["output_tokens"] += usage.get("output_tokens") or 0

    def to_report(self) -> dict[str, Any]:
        report: dict[str, Any] = {}
        for model, stats in self.per_model.items():
            price = _price_for(model)
            cost = None
            if price is not None:
                input_price, output_price = price
                input_cost = stats["input_tokens"] / 1_000_000 * input_price
                output_cost = stats["output_tokens"] / 1_000_000 * output_price
                cost = input_cost + output_cost
            report[model] = {**stats, "estimated_cost_usd": cost}
        return report

    def merge(self, report: dict[str, dict[str, Any]]) -> None:
        """他の `to_report()` の結果を積算する（checkpoint 再開でキャッシュを使った分の使用量）。"""
        for model, stats in report.items():
            total = self.per_model.setdefault(model, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
            for key in ("calls", "input_tokens", "output_tokens"):
                total[key] += stats.get(key, 0)


def load_golden_records() -> Iterator[dict[str, Any]]:
    """active な golden を、共通 assertion（rubric）を混ぜた状態で返す。"""
    rubric = load_rubric()
    for path in sorted(_GOLDEN_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        with path.open(encoding="utf-8") as f:
            record = yaml.safe_load(f)
        if record.get("status") == "active":
            record["assertions"] = merge_assertions(record["assertions"], rubric)
            # instance がまだ 1 件も無いファイルは `instances:` が None になる（起票直後の状態）
            record["instances"] = record["instances"] or []
            yield record


def validate_check_fingerprints() -> dict[str, str]:
    in_use: dict[str, str] = {}
    stale: list[str] = []
    for record in load_golden_records():
        for assertion in record["assertions"]:
            if assertion["type"] != "deterministic":
                continue
            current = check_fingerprint(assertion["check"])
            in_use[assertion["check"]] = current
            if assertion.get("check_fingerprint") != current:
                stale.append(
                    f"  {record['failure_mode']}/{assertion['id']}: check={assertion['check']} "
                    f"recorded={assertion.get('check_fingerprint')!r} current={current!r}"
                )
    if stale:
        raise ValueError(
            "deterministic check の実装が golden 記録時から変わっている。criterion を読み直し、"
            "必要なら human_verdicts を付け直してから check_fingerprint を更新すること:\n" + "\n".join(stale)
        )
    return in_use


def validate_human_verdicts(records: list[dict[str, Any]]) -> None:
    """人間ラベルのキー集合と値を採点前に検証する。

    どちらも壊れても実行時エラーにならない: 余分なキーは誰も読まず、`pass` / `fail` / `na` 以外の値は
    混同行列のどのセルにも入らないまま分母にだけ残り、TPR / TNR と校正ゲートを 100% のまま通す。
    """
    problems: list[str] = []
    for record in records:
        declared = {assertion["id"] for assertion in record["assertions"]}
        for instance in record["instances"]:
            label = f"{record['failure_mode']}/{instance['source_trace_id']}"
            verdicts = instance["human_verdicts"]
            if missing := sorted(declared - set(verdicts)):
                problems.append(f"  {label}: human_verdicts にラベルが無い assertion: {', '.join(missing)}")
            if extra := sorted(set(verdicts) - declared):
                problems.append(f"  {label}: assertions に無い id へのラベル: {', '.join(extra)}")
            problems.extend(
                f"  {label}/{assertion_id}: 不正な verdict {verdict!r}"
                for assertion_id, verdict in sorted(verdicts.items())
                if verdict not in _VALID_VERDICTS
            )
    if problems:
        raise ValueError(
            f"golden の human_verdicts が不正（verdict は {'/'.join(sorted(_VALID_VERDICTS))} のみ）:\n"
            + "\n".join(problems)
        )


def load_source_records() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    with _JSONL_PATH.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record: dict[str, Any] = json.loads(line)
                records[record["id"]] = record
    return records


def get_source_trace(trace_id: str, sources: dict[str, dict[str, Any]]) -> SourceTrace:
    try:
        record = sources[trace_id]
    except KeyError as exc:
        raise ValueError(f"unknown source_trace_id: {trace_id} not in {_JSONL_PATH}") from exc
    return SourceTrace(
        trace_id=trace_id,
        turn=record["turn"],
        meta=record["meta"],
        input=record["input"],
        observed_output=record["output"],
        turn_decision=record.get("turn_decision"),
        has_turn_decision="turn_decision" in record,
    )


def replay_blocker(trace: SourceTrace, replay_mode: str = "full") -> str | None:
    """本番のターンを忠実に再現できない理由。再現できるなら None。

    手で書いたレコードは `conversation_history` が本番の `messages` と 1:1 になっておらず
    （トピック発話や learning_start の応答が欠けている）、`classify_user_intent` の判定と
    プロンプトの直近履歴が本番と変わる。capture 由来だけが 1:1 を保証できる。
    """
    if trace.meta.get("captured_by") != CAPTURED_BY:
        return "capture 由来でないため conversation_history が本番の state と 1:1 でない"
    if replay_mode == "pinned" and not trace.has_turn_decision:
        return "turn_decision を持たないため、そのターンの決定を注入できない"
    return None


def to_turn_plan(trace: SourceTrace) -> TurnPlan:
    """保存済みの決定内容から、そのターンがプロンプトへ注入した値を組み直す。

    `observations` は `covered_aspects` にマージ済みなので保存しておらず、ここでは空で足りる
    （プロンプトが読むのは response_mode / selected_aspect / error_summary だけ）。
    """
    decision = trace.turn_decision
    if decision is None:
        graph_state = trace.input["graph_state"]
        return TurnPlan(covered_aspects=list(graph_state.get("covered_aspects") or []))
    return TurnPlan(
        covered_aspects=list(decision.get("covered_aspects") or []),
        analysis=DialogueTurnAnalysis(
            observations=[],
            response_mode=decision["response_mode"],
            selected_aspect=decision["selected_aspect"],
            # 改訂前に capture したレコードはこのキーを持たない（そのターンは誤り未検出として再生する）
            has_misconception=decision.get("has_misconception", False),
            error_summary=decision["error_summary"],
        ),
        wrap_up=bool(decision.get("wrap_up", False)),
    )


def to_map_turn_plan(trace: SourceTrace) -> MapTurnPlan:
    decision = trace.turn_decision
    if decision is None:
        graph_state = trace.input["graph_state"]
        return MapTurnPlan(
            depth_map=graph_state["depth_map"],
            map_covered=list(graph_state.get("map_covered") or []),
        )
    return MapTurnPlan(
        depth_map=decision["depth_map"],
        map_covered=list(decision["map_covered"]),
        analysis=MapDialogueTurnAnalysis(
            observations=[],
            has_misconception=decision["has_misconception"],
            error_summary=decision["error_summary"],
            response_mode=decision["response_mode"],
            selected_aspect_id=decision["selected_aspect_id"],
        ),
        wrap_up=bool(decision["wrap_up"]),
    )


def to_state(trace: SourceTrace) -> LearningState:
    graph_state = trace.input["graph_state"]
    messages: list[BaseMessage] = [
        AIMessage(content=m["content"]) if m["role"] == "assistant" else HumanMessage(content=m["content"])
        for m in trace.input["conversation_history"]
    ]
    state: LearningState = {
        "user_id": _EVAL_USER_ID,
        "dialogue_session_id": uuid4(),
        "note_id": uuid4(),
        "messages": messages,
        "topic": graph_state["topic"],
        "turn_count": graph_state.get("turn_count") or trace.turn,
        "should_generate_note": False,
        "session_type": "learning",
    }
    if graph_state.get("learning_goal"):
        state["learning_goal"] = graph_state["learning_goal"]
    if graph_state.get("focus_aspects"):
        state["focus_aspects"] = graph_state["focus_aspects"]
    if graph_state.get("covered_aspects"):
        state["covered_aspects"] = graph_state["covered_aspects"]
    state["wrap_up_offered"] = bool(graph_state.get("wrap_up_offered", True))
    if trace_route(trace) == MAP_ROUTE:
        _add_map_state(state, graph_state)
    return state


def _add_map_state(state: LearningState, graph_state: dict[str, Any]) -> None:
    state["intake_complete"] = True
    state["depth_map"] = graph_state["depth_map"]
    state["map_covered"] = list(graph_state.get("map_covered") or [])
    state["intake_message_count"] = graph_state["intake_message_count"]
    state["wrap_up_offered"] = bool(graph_state["wrap_up_offered"])
    if graph_state.get("learning_source"):
        state["learning_source"] = graph_state["learning_source"]
    if graph_state.get("prior_knowledge"):
        state["prior_knowledge"] = graph_state["prior_knowledge"]


def message_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            parts.append(str(block.get("text", "")))
    return "".join(parts)


async def _generate_output_once(trace: SourceTrace, replay_mode: str) -> Generation:
    state = to_state(trace)
    if replay_mode != "pinned":
        result = await learning_dialogue(state)
    elif trace_route(trace) == MAP_ROUTE:
        result = await respond_map(state, to_map_turn_plan(trace))
    else:
        result = await respond(state, to_turn_plan(trace))
    return Generation(
        output=message_text(result["messages"][0]),
        turn_analysis=result.get("turn_analysis"),
        covered_aspects=list(result.get("covered_aspects") or []),
        turn_count=result["turn_count"],
        map_covered=list(result.get("map_covered") or []),
        depth_map=result.get("depth_map"),
    )


async def generate_output(trace: SourceTrace, replay_mode: str = "full") -> Generation:
    """本番の対話ノードを呼んで応答を作り直す（regression モード）。

    `full` は事前分析込みで実行するのでプロンプト改訂の効果と分析の揺れが両方入る。
    `pinned` は保存済みの決定（`turn_decision`）を注入して応答生成だけを再実行するので、
    分析の揺れを除いた「プロンプトを直した効果」だけが見える。

    接続断・タイムアウト・レート制限・5xx はバックオフして最大 `_GENERATE_MAX_ATTEMPTS` 回まで
    再試行する（生成は同じ入力を投げ直すだけで冪等）。課金枯渇は再試行しても直らないので
    `QuotaExhausted` を送出し、呼び出し元（`run`）で実行全体を止める。
    """
    last_error: Exception | None = None
    for attempt in range(1, _GENERATE_MAX_ATTEMPTS + 1):
        try:
            return await _generate_output_once(trace, replay_mode)
        except Exception as exc:
            if _is_quota_exhausted(exc):
                raise QuotaExhausted(str(exc)) from exc
            if not _is_transient(exc) or attempt == _GENERATE_MAX_ATTEMPTS:
                raise
            last_error = exc
            logger.warning("generate_output attempt %d/%d raised: %s", attempt, _GENERATE_MAX_ATTEMPTS, exc)
            await asyncio.sleep(_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
    assert last_error is not None  # ループは return か raise で必ず抜ける
    raise last_error


def to_verdict(polarity: str, holds: bool) -> str:
    if polarity == "must":
        return "pass" if holds else "fail"
    if polarity == "must_not":
        return "fail" if holds else "pass"
    raise ValueError(f"unknown polarity: {polarity!r} (expected 'must' or 'must_not')")


def should_escalate(polarity: str, holds: bool) -> bool:
    """screen の判定を confirm に回すべきか。verdict（polarity 適用後）が fail のときだけ回す。

    「良いものを fail と言う」誤り（TNR を壊す FP）だけを confirm に回す設計。
    screen が pass と言ったもの（FN の可能性）は confirm に届かない。
    """
    return to_verdict(polarity, holds) == "fail"


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    """二項比率の Wilson score 95%（既定）信頼区間。標本が無ければ None。"""
    if total == 0:
        return None
    phat = successes / total
    denom = 1 + z**2 / total
    center = phat + z**2 / (2 * total)
    margin = z * math.sqrt(phat * (1 - phat) / total + z**2 / (4 * total**2))
    lower = (center - margin) / denom
    upper = (center + margin) / denom
    return max(0.0, lower), min(1.0, upper)


def aggregate_verdict(outcomes: list[AssertionOutcome]) -> str:
    """must が満たされ must_not が現れていなければ pass。適用外（na）は中立。"""
    scored = [o for o in outcomes if o.applicable]
    return "pass" if all(o.verdict == "pass" for o in scored) else "fail"


def format_conversation(conversation_history: list[dict[str, str]]) -> str:
    return "\n".join(f"{turn['role']}: {turn['content']}" for turn in conversation_history)


async def judge_by_llm(
    assertion: dict[str, Any],
    trace: SourceTrace,
    output: str,
    judge: BaseChatModel,
    usage: JudgeUsage | None = None,
) -> JudgeResult:
    """1 criterion を二値で判定する。

    judge は必須フィールド `holds` を落とした tool_call を返すことがある。temperature 0 では
    同じプロンプトを投げ直しても同じ欠落が再現するため、リトライでは欠けたフィールドを
    名指しした追記を足して入力を変える。

    `method="json_schema"` を明示するのは、既定の `function_calling`（強制 tool_choice）が
    claude-opus-5-5 では 400 エラーになるため（他の judge モデルでは両方式とも動く）。
    """
    prompt = JUDGE_PROMPT.format(
        topic=trace.input["graph_state"]["topic"],
        conversation=format_conversation(trace.input["conversation_history"]),
        observed_output=output,
        criterion=assertion["criterion"].strip(),
    )
    runnable = judge.with_structured_output(JudgeResult, include_raw=True, method="json_schema")
    model_name = judge_model_name(judge)

    last_error: str = "unknown"
    for attempt in range(1, _JUDGE_MAX_ATTEMPTS + 1):
        content = prompt if attempt == 1 else f"{prompt}\n{JUDGE_RETRY_SUFFIX.format(error=last_error)}"
        try:
            result = await runnable.ainvoke([HumanMessage(content=content)])
        except Exception as exc:
            if _is_quota_exhausted(exc):
                raise QuotaExhausted(str(exc)) from exc
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("judge attempt %d/%d raised for %s", attempt, _JUDGE_MAX_ATTEMPTS, assertion["id"])
            continue
        if usage is not None:
            usage.record(model_name, result.get("raw") if isinstance(result, dict) else None)
        parsed = result["parsed"] if isinstance(result, dict) else result
        if isinstance(parsed, JudgeResult):
            return parsed
        last_error = str(result["parsing_error"]) if isinstance(result, dict) else "judge returned no JudgeResult"
        logger.warning("judge attempt %d/%d unparsable for %s", attempt, _JUDGE_MAX_ATTEMPTS, assertion["id"])

    raise RuntimeError(
        f"judge failed for assertion {assertion['id']} after {_JUDGE_MAX_ATTEMPTS} attempts: {last_error}"
    )


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

    if declared == _NOT_APPLICABLE:
        return AssertionOutcome(
            assertion_id=assertion["id"],
            assertion_type=assertion["type"],
            polarity=assertion["polarity"],
            holds=None,
            verdict=_NOT_APPLICABLE,
            human_verdict=human_verdict,
            detail=f"applies_when: {assertion.get('applies_when', '').strip()}",
            decided_by=_NOT_APPLICABLE,
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
        outcome = run_check(assertion["check"], output)
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


def assertion_pass_rates(results: list[InstanceResult]) -> list[dict[str, Any]]:
    rates: list[dict[str, Any]] = []
    for result in results:
        by_assertion: dict[str, list[str]] = {}
        scopes: dict[str, str] = {}
        for run in result.runs:
            for outcome in run.outcomes:
                by_assertion.setdefault(outcome.assertion_id, []).append(outcome.verdict)
                scopes[outcome.assertion_id] = outcome.scope
        for assertion_id, verdicts in by_assertion.items():
            scored = [v for v in verdicts if v != _NOT_APPLICABLE]
            rates.append(
                {
                    "failure_mode": result.failure_mode,
                    "source_trace_id": result.source_trace_id,
                    "assertion_id": assertion_id,
                    "scope": scopes[assertion_id],
                    "runs": len(verdicts),
                    "not_applicable": len(verdicts) - len(scored),
                    "passed": sum(1 for v in scored if v == "pass"),
                    "pass_rate": (sum(1 for v in scored if v == "pass") / len(scored)) if scored else None,
                }
            )
    return rates


def rubric_pass_rates(results: list[InstanceResult]) -> list[dict[str, Any]]:
    """共通 assertion の pass 率。failure_mode をまたぐので instance 単位では束ねない。"""
    by_assertion: dict[str, list[str]] = {}
    for result in results:
        for run in result.runs:
            for outcome in run.outcomes:
                if outcome.scope == RUBRIC_SCOPE:
                    by_assertion.setdefault(outcome.assertion_id, []).append(outcome.verdict)
    rates: list[dict[str, Any]] = []
    for assertion_id, verdicts in sorted(by_assertion.items()):
        scored = [v for v in verdicts if v != _NOT_APPLICABLE]
        rates.append(
            {
                "assertion_id": assertion_id,
                "runs": len(verdicts),
                "not_applicable": len(verdicts) - len(scored),
                "passed": sum(1 for v in scored if v == "pass"),
                "pass_rate": (sum(1 for v in scored if v == "pass") / len(scored)) if scored else None,
            }
        )
    return rates


def failure_mode_pass_rates(results: list[InstanceResult]) -> list[dict[str, Any]]:
    by_mode: dict[str, list[str]] = {}
    for result in results:
        for run in result.runs:
            by_mode.setdefault(result.failure_mode, []).append(run.verdict)
    return [
        {
            "failure_mode": mode,
            "runs": len(verdicts),
            "passed": sum(1 for v in verdicts if v == "pass"),
            "pass_rate": sum(1 for v in verdicts if v == "pass") / len(verdicts),
        }
        for mode, verdicts in sorted(by_mode.items())
    ]


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def _coverage_ids(generation: Generation) -> set[str]:
    if generation.depth_map is not None:
        return {c["aspect_id"] for c in generation.map_covered}
    return {a["aspect"] for a in generation.covered_aspects}


def coverage_stability(results: list[InstanceResult]) -> list[dict[str, Any]]:
    """同一入力の run 間で、事前分析が付ける観点名がどれだけ一致するかを測る。

    `merge_coverage` は観点名の文字列をキーに dedup するため、run ごとに粒度が変われば
    多ターンで「既出観点を再質問しない」が静かに壊れる。その揺れを数字にする。
    """
    rows: list[dict[str, Any]] = []
    for result in results:
        aspect_sets = [_coverage_ids(run.generation) for run in result.runs if run.generation is not None]
        if len(aspect_sets) < 2:
            continue
        pairs = [
            _jaccard(aspect_sets[i], aspect_sets[j])
            for i in range(len(aspect_sets))
            for j in range(i + 1, len(aspect_sets))
        ]
        rows.append(
            {
                "failure_mode": result.failure_mode,
                "source_trace_id": result.source_trace_id,
                "runs": len(aspect_sets),
                "mean_jaccard": sum(pairs) / len(pairs),
                "aspect_sets": [sorted(s) for s in aspect_sets],
            }
        )
    return rows


def assertion_agreement(results: list[InstanceResult], *, stage: str = "final") -> dict[str, Any]:
    """judge–人間一致を混同行列で出す。`stage="screen"` はカスケードの screen 単体を見る。

    stage="screen" で applicable / human_verdict の判定は screen ではなく final の値を使う
    （na は applies_when という input の性質で、カスケードの有無に関わらず同じ扱いになるため）。
    """

    def verdict_of(o: AssertionOutcome) -> str:
        return o.screen_verdict if stage == "screen" else o.verdict

    outcomes = [o for r in results for run in r.runs for o in run.outcomes]
    scored = [o for o in outcomes if o.applicable and o.human_verdict]
    tp = sum(1 for o in scored if o.human_verdict == "fail" and verdict_of(o) == "fail")
    fn = sum(1 for o in scored if o.human_verdict == "fail" and verdict_of(o) == "pass")
    fp = sum(1 for o in scored if o.human_verdict == "pass" and verdict_of(o) == "fail")
    tn = sum(1 for o in scored if o.human_verdict == "pass" and verdict_of(o) == "pass")
    total = len(scored)
    return {
        "granularity": "assertion",
        "stage": stage,
        "total": total,
        "agreed": tp + tn,
        "agreement_rate": (tp + tn) / total if total else None,
        "not_applicable": sum(1 for o in outcomes if not o.applicable),
        "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "tpr": tp / (tp + fn) if tp + fn else None,
        "tnr": tn / (tn + fp) if tn + fp else None,
        "mismatches": [
            {
                "failure_mode": r.failure_mode,
                "source_trace_id": r.source_trace_id,
                "assertion_id": o.assertion_id,
                "judged": verdict_of(o),
                "human": o.human_verdict,
                "detail": o.screen_detail if stage == "screen" and o.assertion_type == "judge" else o.detail,
            }
            for r in results
            for run in r.runs
            for o in run.outcomes
            if o.applicable and o.human_verdict and verdict_of(o) != o.human_verdict
        ],
    }


def escalation_summary(results: list[InstanceResult]) -> dict[str, Any]:
    """カスケードで screen から confirm に回った judge assertion の内訳。

    overturned（screen=fail → confirm=pass）は Haiku と Opus が割れた箇所そのもので、
    criterion レビューの入力になる（README.md の規約: 割れたら criterion の曖昧さを疑う）。
    """
    judged = [
        (r, o) for r in results for run in r.runs for o in run.outcomes if o.assertion_type == "judge" and o.applicable
    ]
    escalated = [(r, o) for r, o in judged if o.escalated]
    confirmed_fail = [o for _, o in escalated if o.verdict == "fail"]
    overturned = [o for _, o in escalated if o.verdict == "pass"]
    return {
        "total_judge": len(judged),
        "escalated": len(escalated),
        "confirmed_fail": len(confirmed_fail),
        "overturned_to_pass": len(overturned),
        "overturned": [
            {
                "failure_mode": r.failure_mode,
                "source_trace_id": r.source_trace_id,
                "assertion_id": o.assertion_id,
                "screen_detail": o.screen_detail,
                "confirm_detail": o.detail,
            }
            for r, o in escalated
            if o.verdict == "pass"
        ],
    }


def record_agreement(results: list[InstanceResult]) -> dict[str, Any]:
    """instance 全体の pass/fail を人間ラベル（instance["pass"]）と突き合わせる。"""
    pairs = [
        (run.verdict, "pass" if r.human_pass else "fail")
        for r in results
        if r.human_pass is not None
        for run in r.runs
    ]
    agreed = sum(1 for judged, human in pairs if judged == human)
    return {
        "granularity": "record",
        "total": len(pairs),
        "agreed": agreed,
        "agreement_rate": agreed / len(pairs) if pairs else None,
        "mismatches": [
            {
                "failure_mode": r.failure_mode,
                "source_trace_id": r.source_trace_id,
                "judged": run.verdict,
                "human": "pass" if r.human_pass else "fail",
            }
            for r in results
            if r.human_pass is not None
            for run in r.runs
            if run.verdict != ("pass" if r.human_pass else "fail")
        ],
    }


def assertion_agreement_rates(results: list[InstanceResult]) -> list[dict[str, Any]]:
    """assertion ごとに instance を跨いで judge–人間一致を集計する。

    pass 率は負例と正例で目標値が逆になり、コーパスの構成を知らないと読めない。
    scoring で見るべきは「judge がラベルと合っているか」なので、目標が常に 100% の指標にする。
    """
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for result in results:
        for run in result.runs:
            for outcome in run.outcomes:
                if not outcome.applicable or not outcome.human_verdict:
                    continue
                key = (result.failure_mode, outcome.assertion_id)
                row = rows.setdefault(
                    key,
                    {"failure_mode": key[0], "assertion_id": key[1], "total": 0, "agreed": 0, "mismatches": []},
                )
                row["total"] += 1
                if outcome.agrees:
                    row["agreed"] += 1
                else:
                    row["mismatches"].append(
                        {
                            "source_trace_id": result.source_trace_id,
                            "judged": outcome.verdict,
                            "human": outcome.human_verdict,
                        }
                    )
    return [rows[key] for key in sorted(rows)]


def calibration_gate(
    results: list[InstanceResult], *, stage: str, tpr_min: float = 0.9, tnr_min: float = 0.9
) -> dict[str, Any]:
    """方向別の合格条件（TPR ≥ tpr_min かつ TNR ≥ tnr_min）で judge を評価する。

    総合一致率だけでは「良いものを fail と言う」偏り（P1）が 90% の下に隠れるため、
    TPR/TNR を別々にゲートする。`stage="final"` のときだけ正例レコードが judge 集約で
    全件 pass になることも要求する（record_agreement とは独立に、この gate 自体で判定する）。
    """
    agreement = assertion_agreement(results, stage=stage)
    matrix = agreement["confusion_matrix"]
    tp, tn, fp, fn = matrix["tp"], matrix["tn"], matrix["fp"], matrix["fn"]
    tpr, tnr = agreement["tpr"], agreement["tnr"]
    tpr_ci = wilson_interval(tp, tp + fn)
    tnr_ci = wilson_interval(tn, tn + fp)

    failures: list[str] = []
    if tpr is None:
        failures.append("TPR: 陽性（人間ラベル fail）の標本が無い")
    elif tpr < tpr_min:
        failures.append(f"TPR {tpr:.0%} が閾値 {tpr_min:.0%} 未満")
        if stage == "screen":
            failures.append("screen の FN はカスケードで救えない（confirm は screen=fail のときだけ動く）")
    if tnr is None:
        failures.append("TNR: 陰性（人間ラベル pass）の標本が無い")
    elif tnr < tnr_min:
        failures.append(f"TNR {tnr:.0%} が閾値 {tnr_min:.0%} 未満")

    positive_records = {"total": 0, "passed": 0}
    if stage == "final":
        positives = [r for r in results if r.human_pass is True]
        positive_records["total"] = len(positives)
        positive_records["passed"] = sum(1 for r in positives if all(run.verdict == "pass" for run in r.runs))
        if positive_records["total"] and positive_records["passed"] < positive_records["total"]:
            failures.append(
                f"正例レコードが judge 集約で全件 pass にならない "
                f"({positive_records['passed']}/{positive_records['total']})"
            )

    return {
        "stage": stage,
        "tpr": tpr,
        "tpr_ci95": tpr_ci,
        "tnr": tnr,
        "tnr_ci95": tnr_ci,
        "positive_records": positive_records,
        "passed": not failures,
        "failures": failures,
    }


def _instance_kind(human_pass: bool | None) -> str:
    if human_pass is None:
        return "未ラベル"
    return "正例" if human_pass else "負例"


def print_scoring_summary(report: dict[str, Any]) -> None:
    print("レコード別判定（judge の集約 vs 人間ラベル）")
    for record in report["records"]:
        human = "-" if record["human_pass"] is None else ("pass" if record["human_pass"] else "fail")
        for run in record["runs"]:
            mark = "OK" if human != "-" and run["verdict"] == human else "NG"
            print(
                f"  {record['source_trace_id']:<45} {_instance_kind(record['human_pass']):<6} "
                f"judged={run['verdict']:<5} human={human:<5} {mark}"
            )
    record_agreement_result = report["agreement"]["record"]
    rate = record_agreement_result["agreement_rate"]
    suffix = f" ({rate:.0%})" if rate is not None else ""
    print(f"{' ' * 66}一致 {record_agreement_result['agreed']}/{record_agreement_result['total']}{suffix}")

    print("\nassertion 別 一致")
    for row in report["agreement"]["by_assertion"]:
        print(f"  {row['failure_mode']:<38} {row['assertion_id']:<4} {row['agreed']}/{row['total']}")
        for mismatch in row["mismatches"]:
            print(f"      NG {mismatch['source_trace_id']}  judged={mismatch['judged']} human={mismatch['human']}")

    def _print_agreement(label: str, agreement: dict[str, Any]) -> None:
        matrix = agreement["confusion_matrix"]
        rate = agreement["agreement_rate"]
        suffix = f" ({rate:.0%})" if rate is not None else ""
        print(f"\njudge–人間一致（{label}）: {agreement['agreed']}/{agreement['total']}{suffix}")
        counts = f"TP={matrix['tp']} TN={matrix['tn']} FP={matrix['fp']} FN={matrix['fn']}"
        print(f"  {counts}   （陽性 = 人間ラベル fail）")
        print(f"  TPR={agreement['tpr']:.0%}" if agreement["tpr"] is not None else "  TPR=n/a")
        print(f"  TNR={agreement['tnr']:.0%}" if agreement["tnr"] is not None else "  TNR=n/a")
        print(f"  適用外（applies_when を満たさず採点対象外）: {agreement['not_applicable']} 件")

    screen_model = report["meta"]["judge"]["screen"]
    confirm_model = report["meta"]["judge"]["confirm"]
    cascade_enabled = confirm_model is not None

    if cascade_enabled:
        _print_agreement(f"screen={screen_model} 単体", report["agreement"]["screen_assertion"])
        _print_agreement(f"final（screen={screen_model} → confirm={confirm_model}）", report["agreement"]["assertion"])
    else:
        _print_agreement(f"assertion 単位・judge={screen_model}", report["agreement"]["assertion"])

    if cascade_enabled:
        esc = report["agreement"]["escalations"]
        print(
            f"\nエスカレーション: {esc['escalated']}/{esc['total_judge']} 件"
            f"（fail 確定 {esc['confirmed_fail']} / pass に覆った {esc['overturned_to_pass']}）"
        )
        for item in esc["overturned"]:
            print(f"  覆った: {item['failure_mode']}/{item['source_trace_id']} {item['assertion_id']}")
            print(f"    screen ({screen_model}) : {item['screen_detail']}")
            print(f"    confirm({confirm_model}): {item['confirm_detail']}")

    for stage in (("screen",) if cascade_enabled else ()) + ("final",):
        gate = report["agreement"]["calibration"][stage]
        tpr = f"{gate['tpr']:.0%}" if gate["tpr"] is not None else "n/a"
        tnr = f"{gate['tnr']:.0%}" if gate["tnr"] is not None else "n/a"
        tpr_ci = f" [{gate['tpr_ci95'][0]:.0%},{gate['tpr_ci95'][1]:.0%}]" if gate["tpr_ci95"] else ""
        tnr_ci = f" [{gate['tnr_ci95'][0]:.0%},{gate['tnr_ci95'][1]:.0%}]" if gate["tnr_ci95"] else ""
        status = "PASS" if gate["passed"] else "FAIL"
        print(f"\n校正ゲート（{stage}）: {status}  TPR={tpr}{tpr_ci}  TNR={tnr}{tnr_ci}")
        if stage == "final" and gate["positive_records"]["total"]:
            print(f"  正例レコード: {gate['positive_records']['passed']}/{gate['positive_records']['total']} pass")
        for reason in gate["failures"]:
            print(f"  NG {reason}")

    print_judge_usage(report)


def print_judge_usage(report: dict[str, Any]) -> None:
    usage = report["meta"]["judge_usage"]
    if not usage:
        return
    print("\njudge トークン使用量")
    for model, stats in usage.items():
        cost = f"${stats['estimated_cost_usd']:.4f}" if stats["estimated_cost_usd"] is not None else "n/a"
        print(
            f"  {model:<30} calls={stats['calls']:<4} "
            f"input={stats['input_tokens']:<8} output={stats['output_tokens']:<8} cost≈{cost}"
        )


def print_regression_summary(report: dict[str, Any]) -> None:
    meta = report["meta"]
    print(f"失敗モード別 pass 率（{meta['runs']} 回生成 / replay={meta['replay_mode']} / route={meta['route']}）")
    for row in report["aggregate"]["failure_mode_pass_rates"]:
        print(f"  {row['failure_mode']:<38} {row['passed']}/{row['runs']} ({row['pass_rate']:.0%})")

    print("\nassertion 別 pass 率")
    for row in report["aggregate"]["assertion_pass_rates"]:
        rate = f"{row['pass_rate']:.0%}" if row["pass_rate"] is not None else "n/a"
        na = f"  na={row['not_applicable']}" if row["not_applicable"] else ""
        print(
            f"  {row['source_trace_id']:<45} {row['assertion_id']:<4} "
            f"{row['passed']}/{row['runs'] - row['not_applicable']} ({rate}){na}"
        )
    stability = report["aggregate"]["coverage_stability"]
    if stability:
        print("\n観点名の run 間一致（事前分析の揺れ。1.0 なら毎回同じ観点セット）")
        for row in stability:
            print(f"  {row['source_trace_id']:<45} mean_jaccard={row['mean_jaccard']:.2f}")
            for aspects in row["aspect_sets"]:
                print(f"      {aspects}")

    if report["skipped"]:
        print("\n忠実に再現できないためスキップしたインスタンス")
        for item in report["skipped"]:
            print(f"  {item['failure_mode']}/{item['source_trace_id']}: {item['reason']}")
    print("\n人間ラベルが無いため judge–人間一致は算出しない（scoring モードで校正する）。")
    print_judge_usage(report)


def print_summary(report: dict[str, Any]) -> None:
    print("=" * 100)
    if report["meta"]["mode"] == "scoring":
        print_scoring_summary(report)
    else:
        print_regression_summary(report)

    if report["errors"]:
        print("\nエラー")
        for err in report["errors"]:
            print(f"  {err}")


def build_report(
    results: list[InstanceResult],
    errors: list[str],
    *,
    mode: str,
    runs: int,
    fingerprints: dict[str, str],
    judge: BaseChatModel,
    confirm_judge: BaseChatModel | None = None,
    usage: JudgeUsage | None = None,
    skipped: list[dict[str, str]] | None = None,
    replay_mode: str = "full",
    route: str = ALL_ROUTES,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "meta": {
            "mode": mode,
            "runs": runs if mode == "regression" else 1,
            "replay_mode": replay_mode if mode == "regression" else None,
            "generated_at": datetime.now(UTC).isoformat(),
            "model": llm.model_name,
            "temperature": llm.temperature,
            "prompt_version": PROMPT_VERSION,
            "prompt_fingerprint": PROMPT_FINGERPRINT,
            "map_prompt_fingerprint": MAP_PROMPT_FINGERPRINT,
            "route": route,
            "judge_model": judge_model_name(judge),
            "judge": {
                "screen": judge_model_name(judge),
                "confirm": judge_model_name(confirm_judge) if confirm_judge is not None else None,
            },
            "judge_usage": usage.to_report() if usage is not None else {},
            "check_fingerprints": fingerprints,
        },
        "records": [
            {
                "failure_mode": r.failure_mode,
                "source_trace_id": r.source_trace_id,
                "human_pass": r.human_pass,
                "runs": [
                    {
                        "run_index": run.run_index,
                        "verdict": run.verdict,
                        "output": run.output,
                        "turn_analysis": run.generation.turn_analysis if run.generation else None,
                        "covered_aspects": run.generation.covered_aspects if run.generation else None,
                        "map_covered": run.generation.map_covered if run.generation else None,
                        "depth_map": run.generation.depth_map if run.generation else None,
                        "assertions": [
                            {
                                "assertion_id": o.assertion_id,
                                "type": o.assertion_type,
                                "polarity": o.polarity,
                                "holds": o.holds,
                                "judged": o.verdict,
                                "human": o.human_verdict or None,
                                "detail": o.detail,
                                "decided_by": o.decided_by,
                                "screen_holds": o.screen_holds,
                                "screen_detail": o.screen_detail or None,
                            }
                            for o in run.outcomes
                        ],
                    }
                    for run in r.runs
                ],
            }
            for r in results
        ],
        "aggregate": {
            "assertion_pass_rates": assertion_pass_rates(results),
            "rubric_pass_rates": rubric_pass_rates(results),
            "failure_mode_pass_rates": failure_mode_pass_rates(results),
            "coverage_stability": coverage_stability(results),
        },
        "errors": errors,
        "skipped": skipped or [],
    }
    if mode == "scoring":
        report["agreement"] = {
            "assertion": assertion_agreement(results, stage="final"),
            "screen_assertion": assertion_agreement(results, stage="screen"),
            "record": record_agreement(results),
            "by_assertion": assertion_agreement_rates(results),
            "escalations": escalation_summary(results),
            "calibration": {
                "final": calibration_gate(results, stage="final"),
                "screen": calibration_gate(results, stage="screen"),
            },
        }
    return report


def unannotated_ids(sources: dict[str, dict[str, Any]]) -> list[str]:
    """人間ラベル（`pass`）が付いていないレコードの id。"""
    return [record["id"] for record in sources.values() if record.get("pass") is None]


def next_rerun_id(source_trace_id: str, existing: set[str]) -> str:
    """`{元 id}-rerun{連番}` の空き番号を返す。採取セッションを重ねても既存 id を踏まない。"""
    index = 1
    while f"{source_trace_id}-rerun{index:02d}" in existing:
        index += 1
    return f"{source_trace_id}-rerun{index:02d}"


def _rerun_meta(base_meta: dict[str, Any]) -> dict[str, Any]:
    is_map = base_meta.get("route") == MAP_ROUTE
    meta: dict[str, Any] = {"model": llm.model_name}
    if not is_map:
        meta["prompt_version"] = PROMPT_VERSION
    meta["prompt_fingerprint"] = MAP_PROMPT_FINGERPRINT if is_map else PROMPT_FINGERPRINT
    meta["params"] = {"temperature": llm.temperature}
    if captured_by := base_meta.get("captured_by"):
        meta["captured_by"] = captured_by
    if is_map:
        meta["route"] = MAP_ROUTE
    return meta


def emit_jsonl(path: Path, results: list[InstanceResult], sources: dict[str, dict[str, Any]]) -> list[str]:
    """regression の生成を正本 jsonl へ追記する。input は元 instance のものを引き継ぐ。

    既存行は書き換えず追記だけする（近傍事例の採取が主目的で、annotate は人間が後から行う）。
    """
    existing = set(sources)
    written: list[str] = []
    with path.open("a", encoding="utf-8") as f:
        for result in results:
            base = sources[result.source_trace_id]
            for run in result.runs:
                if run.generation is None:
                    continue
                trace_id = next_rerun_id(result.source_trace_id, existing)
                # input は元レコードのものをそのまま引き継ぐ（生成後の値を書くと、この行を
                # 再度 regression にかけたとき coverage が二重に入る）。
                record = {
                    "id": trace_id,
                    "schema_version": base["schema_version"],
                    "source": "rerun",
                    "session": base["session"],
                    "dialogue_session_id": None,
                    "turn": base["turn"],
                    "captured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "meta": _rerun_meta(base["meta"]),
                    "input": {
                        "conversation_history": base["input"]["conversation_history"],
                        "graph_state": base["input"]["graph_state"],
                    },
                    "output": run.generation.output,
                    "turn_decision": run.generation.turn_decision(),
                    "pass": None,
                    "first_failure": None,
                    "note": f"regression 再実行（{result.source_trace_id} の入力を再利用）。未 annotate",
                    "annotated_at": None,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                existing.add(trace_id)
                written.append(trace_id)
    return written


def build_manifest(
    mode: str,
    runs: int,
    replay_mode: str,
    judge: BaseChatModel,
    confirm_judge: BaseChatModel | None,
    fingerprints: dict[str, str],
    route: str = ALL_ROUTES,
) -> dict[str, Any]:
    """checkpoint の実行条件。いずれかが変われば再開を拒否する（`CheckpointStore.ensure_manifest`）。"""
    return {
        "mode": mode,
        "runs": runs,
        "replay_mode": replay_mode,
        "route": route,
        "judge_screen": judge_model_name(judge),
        "judge_confirm": judge_model_name(confirm_judge) if confirm_judge is not None else None,
        "model": llm.model_name,
        "temperature": llm.temperature,
        "prompt_version": PROMPT_VERSION,
        "prompt_fingerprint": PROMPT_FINGERPRINT,
        "map_prompt_fingerprint": MAP_PROMPT_FINGERPRINT,
        "check_fingerprints": fingerprints,
        "dataset_content_sha256": dataset_content_hash(_GOLDEN_DIR, _RUBRIC_DIR),
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
) -> tuple[list[InstanceResult], list[str], dict[str, str], JudgeUsage, list[dict[str, str]]]:
    fingerprints = validate_check_fingerprints()
    records = list(load_golden_records())
    validate_human_verdicts(records)
    sources = load_source_records()
    usage = JudgeUsage()
    if checkpoint is not None:
        checkpoint.ensure_manifest(
            build_manifest(mode, runs, replay_mode, judge, confirm_judge, fingerprints, route=route)
        )

    results: list[InstanceResult] = []
    errors: list[str] = []
    skipped: list[dict[str, str]] = []
    for record in records:
        seen_inputs: set[str] = set()
        for instance in record["instances"]:
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
        "--confirm-judge-model",
        default=None,
        help=f"confirm（2段目）に使う Anthropic モデル（既定は {_DEFAULT_CONFIRM_MODEL}）。"
        "screen が fail と判定した judge assertion だけ確認に回す（--no-cascade で無効化）",
    )
    parser.add_argument(
        "--no-cascade",
        action="store_true",
        help="confirm 段を無効化し、screen 単体の判定を最終値にする（従来の単一 judge 相当）",
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

    judge = resolve_judge(args.judge_model)
    confirm_judge = resolve_confirm_judge(args.confirm_judge_model, cascade=not args.no_cascade)
    print(f"mode={args.mode} model={llm.model_name} temperature={llm.temperature}")
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
