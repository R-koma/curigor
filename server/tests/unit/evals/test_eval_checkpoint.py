"""checkpoint 保存・再開・一時的エラーの再試行・課金枯渇の検知（B-9 / open-issues C-2）。

judge 呼び出しと生成は本物の API を叩くため、ここでは内部関数（`_generate_output_once` /
`generate_output` / `evaluate_output` / judge の runnable）を差し替えて経路だけを確認する。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from evals import eval as ev
from evals.checkpoint import CheckpointStore, ManifestMismatch, dataset_content_hash
from graph.llm import llm_judge


class _APIConnectionError(Exception):
    """`type(exc).__name__` 判定用のダミー（実際の openai/anthropic 例外と同じ名前）。"""


_APIConnectionError.__name__ = "APIConnectionError"


class _RateLimitError(Exception):
    pass


_RateLimitError.__name__ = "RateLimitError"


def _trace(trace_id: str = "t1") -> ev.SourceTrace:
    return ev.SourceTrace(
        trace_id=trace_id,
        turn=1,
        meta={},
        input={"graph_state": {"topic": "x"}, "conversation_history": []},
        observed_output="",
    )


def _outcome(assertion_id: str = "a1", verdict: str = "pass") -> ev.AssertionOutcome:
    return ev.AssertionOutcome(
        assertion_id=assertion_id,
        assertion_type="judge",
        polarity="must",
        holds=verdict == "pass",
        verdict=verdict,
        human_verdict="",
        detail="d",
    )


class TestCheckpointStore:
    def test_manifest_written_on_first_use(self, tmp_path: Path) -> None:
        store = CheckpointStore(tmp_path)
        store.ensure_manifest({"a": 1})
        assert (tmp_path / "manifest.json").exists()

    def test_manifest_matching_conditions_do_not_raise(self, tmp_path: Path) -> None:
        store = CheckpointStore(tmp_path)
        expected = {"a": 1, "b": 2}
        store.ensure_manifest(expected)
        store.ensure_manifest(expected)

    def test_manifest_mismatch_blocks_resume(self, tmp_path: Path) -> None:
        store = CheckpointStore(tmp_path)
        store.ensure_manifest({"prompt_fingerprint": "abc"})
        with pytest.raises(ManifestMismatch):
            store.ensure_manifest({"prompt_fingerprint": "changed"})

    def test_generation_round_trip(self, tmp_path: Path) -> None:
        store = CheckpointStore(tmp_path)
        assert store.load_generation("fm", "trace1", 1) is None
        store.save_generation("fm", "trace1", 1, {"output": "hi"})
        assert store.load_generation("fm", "trace1", 1) == {"output": "hi"}

    def test_score_round_trip(self, tmp_path: Path) -> None:
        store = CheckpointStore(tmp_path)
        assert store.load_score("fm", "trace1", 1) is None
        store.save_score("fm", "trace1", 1, {"generation_sha256": "x", "assertions": []})
        loaded = store.load_score("fm", "trace1", 1)
        assert loaded is not None
        assert loaded["generation_sha256"] == "x"


class TestDatasetContentHash:
    def test_changes_when_yaml_edited(self, tmp_path: Path) -> None:
        golden = tmp_path / "golden"
        golden.mkdir()
        rubric = tmp_path / "rubric"
        rubric.mkdir()
        (golden / "a.yaml").write_text("assertions: []\n")
        before = dataset_content_hash(golden, rubric)
        (golden / "a.yaml").write_text("assertions: [x]\n")
        after = dataset_content_hash(golden, rubric)
        assert before != after

    def test_ignores_template_files(self, tmp_path: Path) -> None:
        golden = tmp_path / "golden"
        golden.mkdir()
        rubric = tmp_path / "rubric"
        rubric.mkdir()
        before = dataset_content_hash(golden, rubric)
        (golden / "_TEMPLATE.yaml").write_text("anything\n")
        after = dataset_content_hash(golden, rubric)
        assert before == after


class TestJudgeUsageMerge:
    def test_adds_raw_counts_and_drops_precomputed_cost(self) -> None:
        usage = ev.JudgeUsage()
        usage.record("claude-haiku-4-5", MagicMock(usage_metadata={"input_tokens": 10, "output_tokens": 5}))
        usage.merge(
            {"claude-haiku-4-5": {"calls": 2, "input_tokens": 20, "output_tokens": 8, "estimated_cost_usd": 0.1}}
        )
        assert usage.per_model["claude-haiku-4-5"] == {"calls": 3, "input_tokens": 30, "output_tokens": 13}


class TestBuildManifest:
    def test_reflects_mode_runs_and_judges(self) -> None:
        manifest = ev.build_manifest("regression", 3, "full", llm_judge, None, {"chk": "abc"})
        assert manifest["mode"] == "regression"
        assert manifest["runs"] == 3
        assert manifest["replay_mode"] == "full"
        assert manifest["judge_screen"] == ev.judge_model_name(llm_judge)
        assert manifest["judge_confirm"] is None
        assert manifest["check_fingerprints"] == {"chk": "abc"}
        assert "dataset_content_sha256" in manifest


class TestGenerateOutputRetry:
    async def test_retries_transient_errors_then_succeeds(self) -> None:
        attempts = {"n": 0}

        async def flaky(_trace: ev.SourceTrace, _replay_mode: str) -> ev.Generation:
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise _APIConnectionError("connection reset")
            return ev.Generation(output="ok", turn_analysis=None, covered_aspects=[], turn_count=1)

        with (
            patch("evals.eval._generate_output_once", side_effect=flaky),
            patch("evals.eval.asyncio.sleep", AsyncMock()),
        ):
            result = await ev.generate_output(_trace(), "full")
        assert result.output == "ok"
        assert attempts["n"] == 3

    async def test_gives_up_immediately_on_non_transient_error(self) -> None:
        attempts = {"n": 0}

        async def boom(_trace: ev.SourceTrace, _replay_mode: str) -> ev.Generation:
            attempts["n"] += 1
            raise ValueError("not transient")

        with patch("evals.eval._generate_output_once", side_effect=boom), pytest.raises(ValueError):
            await ev.generate_output(_trace(), "full")
        assert attempts["n"] == 1

    async def test_raises_quota_exhausted_without_retrying(self) -> None:
        attempts = {"n": 0}

        async def boom(_trace: ev.SourceTrace, _replay_mode: str) -> ev.Generation:
            attempts["n"] += 1
            raise _RateLimitError("insufficient_quota: You exceeded your current quota")

        with patch("evals.eval._generate_output_once", side_effect=boom), pytest.raises(ev.QuotaExhausted):
            await ev.generate_output(_trace(), "full")
        assert attempts["n"] == 1

    async def test_reraises_after_exhausting_all_attempts(self) -> None:
        async def always_flaky(_trace: ev.SourceTrace, _replay_mode: str) -> ev.Generation:
            raise _APIConnectionError("still down")

        with (
            patch("evals.eval._generate_output_once", side_effect=always_flaky),
            patch("evals.eval.asyncio.sleep", AsyncMock()),
            pytest.raises(_APIConnectionError),
        ):
            await ev.generate_output(_trace(), "full")


class TestJudgeByLlmQuota:
    async def test_raises_quota_exhausted_without_retrying_further(self) -> None:
        calls = {"n": 0}

        async def fail(_messages: list[object]) -> None:
            calls["n"] += 1
            raise _RateLimitError("insufficient_quota")

        judge = MagicMock()
        judge.with_structured_output.return_value.ainvoke = AsyncMock(side_effect=fail)

        with pytest.raises(ev.QuotaExhausted):
            await ev.judge_by_llm({"id": "a1", "criterion": "c"}, _trace(), "output", judge)
        assert calls["n"] == 1


class TestEvaluateInstanceRunIsolation:
    async def test_isolates_a_failing_run_and_keeps_the_others(self) -> None:
        record = {"failure_mode": "fm", "assertions": []}
        instance: dict[str, Any] = {"source_trace_id": "t1", "human_verdicts": {}, "pass": None}
        calls = {"n": 0}

        async def flaky_generate(_trace: ev.SourceTrace, _replay_mode: str) -> ev.Generation:
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("boom")
            return ev.Generation(output=f"out{calls['n']}", turn_analysis=None, covered_aspects=[], turn_count=1)

        errors: list[str] = []
        with (
            patch("evals.eval.generate_output", side_effect=flaky_generate),
            patch("evals.eval.evaluate_output", AsyncMock(return_value=[])),
        ):
            result = await ev.evaluate_instance(
                record, instance, _trace(), MagicMock(), mode="regression", runs=3, errors=errors
            )

        assert [run.run_index for run in result.runs] == [1, 3]
        assert len(errors) == 1
        assert "run=2" in errors[0]

    async def test_reraises_quota_exhausted_without_recording_an_error(self) -> None:
        async def boom(_trace: ev.SourceTrace, _replay_mode: str) -> ev.Generation:
            raise ev.QuotaExhausted("no credit")

        record = {"failure_mode": "fm", "assertions": []}
        instance: dict[str, Any] = {"source_trace_id": "t1", "human_verdicts": {}, "pass": None}
        errors: list[str] = []
        with patch("evals.eval.generate_output", side_effect=boom), pytest.raises(ev.QuotaExhausted):
            await ev.evaluate_instance(
                record, instance, _trace(), MagicMock(), mode="regression", runs=2, errors=errors
            )
        assert errors == []


class TestEvaluateInstanceCheckpoint:
    async def test_reuses_checkpointed_generation_across_calls(self, tmp_path: Path) -> None:
        record = {"failure_mode": "fm", "assertions": []}
        instance: dict[str, Any] = {"source_trace_id": "t1", "human_verdicts": {}, "pass": None}
        checkpoint = CheckpointStore(tmp_path)
        calls = {"n": 0}

        async def fake_generate(_trace: ev.SourceTrace, _replay_mode: str) -> ev.Generation:
            calls["n"] += 1
            return ev.Generation(output="same", turn_analysis=None, covered_aspects=[], turn_count=1)

        with (
            patch("evals.eval.generate_output", side_effect=fake_generate),
            patch("evals.eval.evaluate_output", AsyncMock(return_value=[])),
        ):
            for _ in range(2):
                await ev.evaluate_instance(
                    record, instance, _trace(), MagicMock(), mode="regression", runs=1, checkpoint=checkpoint
                )

        assert calls["n"] == 1

    async def test_reuses_checkpointed_score_when_output_unchanged(self, tmp_path: Path) -> None:
        record = {
            "failure_mode": "fm",
            "assertions": [{"id": "a1", "type": "judge", "polarity": "must", "criterion": "c"}],
        }
        instance: dict[str, Any] = {"source_trace_id": "t1", "human_verdicts": {"a1": ""}, "pass": None}
        checkpoint = CheckpointStore(tmp_path)
        judge_calls = {"n": 0}

        async def fake_generate(_trace: ev.SourceTrace, _replay_mode: str) -> ev.Generation:
            return ev.Generation(output="same", turn_analysis=None, covered_aspects=[], turn_count=1)

        async def fake_evaluate_output(*_args: object, **_kwargs: object) -> list[ev.AssertionOutcome]:
            judge_calls["n"] += 1
            return [_outcome()]

        with (
            patch("evals.eval.generate_output", side_effect=fake_generate),
            patch("evals.eval.evaluate_output", side_effect=fake_evaluate_output),
        ):
            for _ in range(2):
                result = await ev.evaluate_instance(
                    record, instance, _trace(), MagicMock(), mode="regression", runs=1, checkpoint=checkpoint
                )

        assert judge_calls["n"] == 1
        assert result.runs[0].outcomes[0].verdict == "pass"

    async def test_rescoress_when_cached_hash_is_stale(self, tmp_path: Path) -> None:
        record = {"failure_mode": "fm", "assertions": []}
        instance: dict[str, Any] = {"source_trace_id": "t1", "human_verdicts": {}, "pass": None}
        checkpoint = CheckpointStore(tmp_path)
        checkpoint.save_score("fm", "t1", 1, {"generation_sha256": "stale", "assertions": [], "judge_usage": {}})
        judge_calls = {"n": 0}

        async def fake_generate(_trace: ev.SourceTrace, _replay_mode: str) -> ev.Generation:
            return ev.Generation(output="fresh", turn_analysis=None, covered_aspects=[], turn_count=1)

        async def fake_evaluate_output(*_args: object, **_kwargs: object) -> list[ev.AssertionOutcome]:
            judge_calls["n"] += 1
            return []

        with (
            patch("evals.eval.generate_output", side_effect=fake_generate),
            patch("evals.eval.evaluate_output", side_effect=fake_evaluate_output),
        ):
            await ev.evaluate_instance(
                record, instance, _trace(), MagicMock(), mode="regression", runs=1, checkpoint=checkpoint
            )

        assert judge_calls["n"] == 1


class TestRunStopsOnQuotaExhaustion:
    async def test_stops_before_the_next_instance(self) -> None:
        records = [
            {
                "failure_mode": "fm",
                "assertions": [],
                "instances": [{"source_trace_id": "t1", "human_verdicts": {}, "pass": None}],
            },
            {
                "failure_mode": "fm",
                "assertions": [],
                "instances": [{"source_trace_id": "t2", "human_verdicts": {}, "pass": None}],
            },
        ]
        sources: dict[str, dict[str, Any]] = {"t1": {}, "t2": {}}
        call_order: list[str] = []

        async def fake_evaluate_instance(
            record: dict[str, object], instance: dict[str, object], trace: object, judge: object, **kwargs: object
        ) -> ev.InstanceResult:
            call_order.append(instance["source_trace_id"])  # type: ignore[arg-type]
            if instance["source_trace_id"] == "t1":
                raise ev.QuotaExhausted("no credit")
            raise AssertionError("must not reach t2 after quota exhaustion")

        with (
            patch("evals.eval.validate_check_fingerprints", return_value={}),
            patch("evals.eval.load_golden_records", return_value=iter(records)),
            patch("evals.eval.validate_human_verdicts"),
            patch("evals.eval.load_source_records", return_value=sources),
            patch("evals.eval.get_source_trace", return_value=_trace()),
            patch("evals.eval.evaluate_instance", side_effect=fake_evaluate_instance),
        ):
            results, errors, _fingerprints, _usage, _skipped = await ev.run("scoring", 1, MagicMock())

        assert call_order == ["t1"]
        assert results == []
        assert any("quota exhausted" in e for e in errors)


class TestRunTraceFilter:
    async def test_only_the_named_traces_are_evaluated(self) -> None:
        records = [
            {
                "failure_mode": "fm",
                "assertions": [],
                "instances": [
                    {"source_trace_id": "t1", "human_verdicts": {}, "pass": None},
                    {"source_trace_id": "t2", "human_verdicts": {}, "pass": None},
                ],
            }
        ]
        evaluated: list[str] = []

        async def fake_evaluate_instance(
            record: dict[str, object], instance: dict[str, object], trace: object, judge: object, **kwargs: object
        ) -> ev.InstanceResult:
            evaluated.append(instance["source_trace_id"])  # type: ignore[arg-type]
            return ev.InstanceResult(failure_mode="fm", source_trace_id="t2", human_pass=None)

        with (
            patch("evals.eval.validate_check_fingerprints", return_value={}),
            patch("evals.eval.load_golden_records", return_value=iter(records)),
            patch("evals.eval.validate_human_verdicts"),
            patch("evals.eval.load_source_records", return_value={"t1": {}, "t2": {}}),
            patch("evals.eval.get_source_trace", return_value=_trace()),
            patch("evals.eval.evaluate_instance", side_effect=fake_evaluate_instance),
        ):
            _results, _errors, _fingerprints, _usage, skipped = await ev.run(
                "scoring", 1, MagicMock(), traces=frozenset({"t2"})
            )

        assert evaluated == ["t2"]
        assert skipped == []

    def test_the_filter_is_part_of_the_run_conditions(self) -> None:
        full = ev.build_manifest("scoring", 1, "full", llm_judge, None, {})
        narrowed = ev.build_manifest("scoring", 1, "full", llm_judge, None, {}, traces=frozenset({"t2", "t1"}))

        assert full["traces"] is None
        assert narrowed["traces"] == ["t1", "t2"]
