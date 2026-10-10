from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from evals.dataset import SourceTrace
from evals.judge import JudgeRefused, JudgeUsage, judge_by_llm, judge_model_name, resolve_judge
from graph.llm import llm_judge


def _trace() -> SourceTrace:
    return SourceTrace(
        trace_id="t1",
        turn=1,
        meta={},
        input={"graph_state": {"topic": "x"}, "conversation_history": []},
        observed_output="",
    )


class TestResolveJudge:
    def test_defaults_to_haiku_4_5_with_temperature_zero(self) -> None:
        assert resolve_judge(None) is llm_judge
        assert llm_judge.model == "claude-haiku-4-5-20251001"
        assert llm_judge.temperature == 0
        assert judge_model_name(llm_judge) == "claude-haiku-4-5-20251001"

    def test_models_that_reject_sampling_get_no_temperature(self) -> None:
        judge = resolve_judge("claude-sonnet-5-5")

        assert getattr(judge, "temperature", None) is None

    def test_effort_is_part_of_the_name_so_cached_verdicts_are_not_shared_across_levels(self) -> None:
        judge = resolve_judge("claude-haiku-5-5", "medium")

        assert getattr(judge, "temperature", None) is None
        assert judge_model_name(judge) == "claude-haiku-5-5@medium"

    def test_older_models_keep_temperature_zero_and_no_effort(self) -> None:
        judge = resolve_judge("claude-haiku-4-5")

        assert getattr(judge, "temperature", None) == 0
        assert judge_model_name(judge) == "claude-haiku-4-5"

    @pytest.mark.parametrize("model", [None, "claude-haiku-4-5"])
    def test_effort_on_a_model_without_effort_is_rejected(self, model: str | None) -> None:
        with pytest.raises(ValueError, match="effort"):
            resolve_judge(model, "low")


class TestJudgeModelName:
    def test_ignores_non_string_effort(self) -> None:
        judge = MagicMock()
        judge.model = "claude-opus-5"

        assert judge_model_name(judge) == "claude-opus-5"


class TestJudgeUsagePrice:
    @pytest.mark.parametrize(
        ("model", "expected"),
        [("claude-haiku-5-5@low", 0.6), ("claude-opus-5-5", 24.0), ("claude-opus-5", 30.0)],
    )
    def test_prices_per_model(self, model: str, expected: float) -> None:
        usage = JudgeUsage()
        usage.record(
            model,
            AIMessage(
                content="",
                usage_metadata={"input_tokens": 1_000_000, "output_tokens": 1_000_000, "total_tokens": 2_000_000},
            ),
        )

        assert usage.to_report()[model]["estimated_cost_usd"] == pytest.approx(expected)


class TestJudgeRefusal:
    async def test_a_refusal_fails_without_retrying(self) -> None:
        metadata = {"stop_reason": "refusal", "stop_details": {"category": "cyber"}}
        raw = AIMessage(content="", response_metadata=metadata)
        judge = MagicMock()
        judge.model = "claude-haiku-5-5"
        judge.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value={"parsed": None, "raw": raw, "parsing_error": "empty"}
        )
        usage = JudgeUsage()

        with pytest.raises(JudgeRefused, match="cyber"):
            await judge_by_llm({"id": "a1", "criterion": "c"}, _trace(), "output", judge, usage)

        assert judge.with_structured_output.return_value.ainvoke.await_count == 1
        assert usage.per_model["claude-haiku-5-5"]["calls"] == 1
