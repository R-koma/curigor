from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from evals import eval as ev
from evals.judge_cache import JudgeCache


def _trace() -> ev.SourceTrace:
    return ev.SourceTrace(
        trace_id="t1",
        turn=1,
        meta={},
        input={"graph_state": {"topic": "x"}, "conversation_history": []},
        observed_output="",
    )


def _judge(holds: bool = True) -> MagicMock:
    judge = MagicMock()
    judge.model = "claude-haiku-4-5"
    judge.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value={"parsed": ev.JudgeResult(reason="r", holds=holds), "raw": None}
    )
    return judge


@pytest.fixture
def cache(tmp_path: Path) -> Iterator[JudgeCache]:
    cache = JudgeCache(tmp_path)
    ev.set_judge_cache(cache)
    yield cache
    ev.set_judge_cache(None)


class TestJudgeCache:
    async def test_the_same_prompt_is_judged_once(self, cache: JudgeCache) -> None:
        judge = _judge()
        usage = ev.JudgeUsage()

        first = await ev.judge_by_llm({"id": "a1", "criterion": "c"}, _trace(), "output", judge, usage)
        second = await ev.judge_by_llm({"id": "a1", "criterion": "c"}, _trace(), "output", judge, usage)

        assert first == second
        assert judge.with_structured_output.return_value.ainvoke.await_count == 1
        assert usage.to_report()["claude-haiku-4-5"]["cache_hits"] == 1

    async def test_a_changed_criterion_is_judged_again(self, cache: JudgeCache) -> None:
        judge = _judge()

        await ev.judge_by_llm({"id": "a1", "criterion": "c"}, _trace(), "output", judge)
        await ev.judge_by_llm({"id": "a1", "criterion": "changed"}, _trace(), "output", judge)

        assert judge.with_structured_output.return_value.ainvoke.await_count == 2

    async def test_another_model_does_not_share_the_judgment(self, cache: JudgeCache) -> None:
        screen, confirm = _judge(holds=True), _judge(holds=False)
        confirm.model = "claude-opus-5"

        await ev.judge_by_llm({"id": "a1", "criterion": "c"}, _trace(), "output", screen)
        confirmed = await ev.judge_by_llm({"id": "a1", "criterion": "c"}, _trace(), "output", confirm)

        assert confirmed.holds is False

    async def test_without_reading_the_cache_the_judge_is_called_and_the_result_is_saved(self, tmp_path: Path) -> None:
        ev.set_judge_cache(JudgeCache(tmp_path))
        await ev.judge_by_llm({"id": "a1", "criterion": "c"}, _trace(), "output", _judge(holds=True))
        ev.set_judge_cache(JudgeCache(tmp_path, read=False))
        fresh = _judge(holds=False)
        try:
            result = await ev.judge_by_llm({"id": "a1", "criterion": "c"}, _trace(), "output", fresh)
            ev.set_judge_cache(JudgeCache(tmp_path))
            reread = await ev.judge_by_llm({"id": "a1", "criterion": "c"}, _trace(), "output", _judge(holds=True))
        finally:
            ev.set_judge_cache(None)

        assert result.holds is False
        assert fresh.with_structured_output.return_value.ainvoke.await_count == 1
        assert reread.holds is False


class TestJudgeUsageCacheHits:
    def test_a_model_used_only_from_the_cache_is_reported(self) -> None:
        usage = ev.JudgeUsage()
        usage.record_cache_hit("claude-opus-5")

        report = usage.to_report()

        assert report["claude-opus-5"]["calls"] == 0
        assert report["claude-opus-5"]["cache_hits"] == 1
        assert report["claude-opus-5"]["estimated_cost_usd"] == 0

    def test_merging_a_report_carries_the_cache_hits(self) -> None:
        usage = ev.JudgeUsage()
        usage.merge({"claude-haiku-4-5": {"calls": 1, "input_tokens": 2, "output_tokens": 3, "cache_hits": 4}})

        assert usage.to_report()["claude-haiku-4-5"]["cache_hits"] == 4
