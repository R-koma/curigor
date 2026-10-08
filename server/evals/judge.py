import logging
from dataclasses import dataclass, field
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel, Field

from evals.dataset import SourceTrace
from evals.judge_cache import JudgeCache
from evals.retry import QuotaExhausted, is_quota_exhausted
from graph.llm import llm_judge

logger = logging.getLogger(__name__)

_JUDGE_MAX_ATTEMPTS = 3


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


_TEMPERATURE_UNSUPPORTED: frozenset[str] = frozenset({"claude-opus-5", "claude-opus-5-5", "claude-sonnet-5"})


def resolve_judge(model: str | None) -> BaseChatModel:
    """`--judge-model` が指定されていればその Anthropic モデルを、無ければ既定の judge を返す。"""
    if model is None:
        return llm_judge
    if model in _TEMPERATURE_UNSUPPORTED:
        return ChatAnthropic(model=model)
    return ChatAnthropic(model=model, temperature=0)


DEFAULT_CONFIRM_MODEL = "claude-opus-5"


def resolve_confirm_judge(model: str | None, *, cascade: bool) -> BaseChatModel | None:
    """`--no-cascade` なら None（従来の単一 judge）。既定の confirm モデルは claude-opus-5。

    claude-opus-5-5 は `--confirm-judge-model` で明示すれば使えるが、既定には採用していない。
    scoring で final TPR が 93%→82%（閾値 90%）に落ちる劣化を 2026-09-26 に確認した
    （screen の正しい fail 判定を pass へ誤って覆す）。
    """
    if not cascade:
        return None
    return resolve_judge(model if model is not None else DEFAULT_CONFIRM_MODEL)


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
    cache_hits: dict[str, int] = field(default_factory=dict)

    def record_cache_hit(self, model: str) -> None:
        self.cache_hits[model] = self.cache_hits.get(model, 0) + 1

    def record(self, model: str, raw: BaseMessage | None) -> None:
        stats = self.per_model.setdefault(model, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
        stats["calls"] += 1
        usage = getattr(raw, "usage_metadata", None) if raw is not None else None
        if usage:
            stats["input_tokens"] += usage.get("input_tokens") or 0
            stats["output_tokens"] += usage.get("output_tokens") or 0

    def to_report(self) -> dict[str, Any]:
        report: dict[str, Any] = {}
        for model in [*self.per_model, *(m for m in self.cache_hits if m not in self.per_model)]:
            stats = self.per_model.get(model, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
            price = _price_for(model)
            cost = None
            if price is not None:
                input_price, output_price = price
                input_cost = stats["input_tokens"] / 1_000_000 * input_price
                output_cost = stats["output_tokens"] / 1_000_000 * output_price
                cost = input_cost + output_cost
            report[model] = {**stats, "cache_hits": self.cache_hits.get(model, 0), "estimated_cost_usd": cost}
        return report

    def merge(self, report: dict[str, dict[str, Any]]) -> None:
        """他の `to_report()` の結果を積算する（checkpoint 再開でキャッシュを使った分の使用量）。"""
        for model, stats in report.items():
            total = self.per_model.setdefault(model, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
            for key in ("calls", "input_tokens", "output_tokens"):
                total[key] += stats.get(key, 0)
            if stats.get("cache_hits"):
                self.cache_hits[model] = self.cache_hits.get(model, 0) + stats["cache_hits"]


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


def format_conversation(conversation_history: list[dict[str, str]]) -> str:
    return "\n".join(f"{turn['role']}: {turn['content']}" for turn in conversation_history)


_judge_cache: JudgeCache | None = None


def set_judge_cache(cache: JudgeCache | None) -> None:
    global _judge_cache
    _judge_cache = cache


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
    model_name = judge_model_name(judge)
    cache_key = JudgeCache.key(model_name, JudgeResult.model_json_schema(), prompt)
    if _judge_cache is not None and (cached := _judge_cache.load(cache_key)) is not None:
        if usage is not None:
            usage.record_cache_hit(model_name)
        return JudgeResult.model_validate(cached)
    runnable = judge.with_structured_output(JudgeResult, include_raw=True, method="json_schema")

    last_error: str = "unknown"
    for attempt in range(1, _JUDGE_MAX_ATTEMPTS + 1):
        content = prompt if attempt == 1 else f"{prompt}\n{JUDGE_RETRY_SUFFIX.format(error=last_error)}"
        try:
            result = await runnable.ainvoke([HumanMessage(content=content)])
        except Exception as exc:
            if is_quota_exhausted(exc):
                raise QuotaExhausted(str(exc)) from exc
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("judge attempt %d/%d raised for %s", attempt, _JUDGE_MAX_ATTEMPTS, assertion["id"])
            continue
        if usage is not None:
            usage.record(model_name, result.get("raw") if isinstance(result, dict) else None)
        parsed = result["parsed"] if isinstance(result, dict) else result
        if isinstance(parsed, JudgeResult):
            if _judge_cache is not None:
                _judge_cache.save(cache_key, parsed.model_dump())
            return parsed
        last_error = str(result["parsing_error"]) if isinstance(result, dict) else "judge returned no JudgeResult"
        logger.warning("judge attempt %d/%d unparsable for %s", attempt, _JUDGE_MAX_ATTEMPTS, assertion["id"])

    raise RuntimeError(
        f"judge failed for assertion {assertion['id']} after {_JUDGE_MAX_ATTEMPTS} attempts: {last_error}"
    )
