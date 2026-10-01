from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from evals import eval as ev
from evals.checkpoint import CheckpointStore
from graph.llm import llm_judge
from graph.nodes.learning_dialogue import TurnPlan

_DEPTH_MAP: dict[str, Any] = {
    "topic": "Pythonのf文字列とstr.formatの違い",
    "aspects": [
        {
            "id": "式の評価方法",
            "name": "式の評価方法",
            "is_core": True,
            "defined_question": "f文字列とstr.formatでは、値や式をどのように指定し、いつ評価するのか？",
            "reasoned_question": "f文字列が埋め込み式をその場で評価するのはなぜか？",
            "applied_question": "式を直接埋め込む場合とテンプレートを再利用する場合をどう使い分けるか？",
        },
        {
            "id": "値の指定と再利用",
            "name": "値の指定と再利用",
            "is_core": True,
            "defined_question": "str.formatの置換フィールドと引数はどう対応付けるのか？",
            "reasoned_question": "テンプレートと値を分けて扱えることは、再利用になぜ役立つのか？",
            "applied_question": "同じ書式の文字列を複数の値で作るなら、どちらを選ぶか？",
        },
    ],
}
_COVERED_BEFORE: list[dict[str, Any]] = [{"aspect_id": "式の評価方法", "reached_stage": "defined"}]
_COVERED_AFTER: list[dict[str, Any]] = [
    {"aspect_id": "式の評価方法", "reached_stage": "defined"},
    {"aspect_id": "値の指定と再利用", "reached_stage": "defined"},
]
_ANALYSIS: dict[str, Any] = {
    "response_mode": "reinforce",
    "selected_aspect": "値の指定と再利用",
    "selected_aspect_id": "値の指定と再利用",
    "has_misconception": True,
    "error_summary": "str.format の {name} は、.format(name=...) で渡した値に置き換わる。",
    "wrap_up": False,
}
_DECISION: dict[str, Any] = {**_ANALYSIS, "depth_map": _DEPTH_MAP, "map_covered": _COVERED_AFTER}
_HISTORY: list[dict[str, str]] = [
    {"role": "user", "content": "Python の f 文字列と str.format の違いを、人に説明できるようになりたい。"},
    {"role": "assistant", "content": "始める前に、少しだけ教えてください。"},
    {"role": "user", "content": "目的: 人に説明できるようになる\n教材: 公式ドキュメント\n今の理解: 使ったことがある"},
    {"role": "assistant", "content": "ここから学習を始めましょう。理解したことを説明してみてください。"},
    {"role": "user", "content": "f 文字列は波括弧 {} の中に変数や式を書くと、その値が埋め込まれます。"},
    {"role": "assistant", "content": "この設計の違いは、どんな場面で役立つと思いますか？"},
    {"role": "user", "content": 'str.format は "{name}" と書くと name という文字がそのまま出力されます。'},
]
_MAP_META: dict[str, Any] = {
    "model": "gpt-6-luna",
    "prompt_fingerprint": "3030eeb04d0a",
    "params": {"temperature": 0.7},
    "captured_by": "capture",
    "route": "map",
}
_LEGACY_COVERED: list[dict[str, Any]] = [{"aspect": "プロセス", "reached_depth": "defined"}]


def _map_graph_state(**overrides: Any) -> dict[str, Any]:
    return {
        "topic": "Pythonのf文字列とstr.formatの違い",
        "learning_goal": "人に説明できるようになる",
        "learning_source": "公式ドキュメント",
        "prior_knowledge": "使ったことがある",
        "focus_aspects": [],
        "depth_map": _DEPTH_MAP,
        "map_covered": _COVERED_BEFORE,
        "intake_message_count": 3,
        "turn_count": 3,
        "wrap_up_offered": False,
        "turn_analysis": {
            "response_mode": "deepen",
            "selected_aspect": "式の評価方法",
            "selected_aspect_id": "式の評価方法",
            "has_misconception": False,
            "error_summary": "",
            "wrap_up": False,
        },
        **overrides,
    }


def _map_trace(
    decision: dict[str, Any] | None,
    *,
    has_turn_decision: bool = True,
    meta: dict[str, Any] | None = None,
    graph_state: dict[str, Any] | None = None,
) -> ev.SourceTrace:
    return ev.SourceTrace(
        trace_id="2026-10-01-04d22b75__t8",
        turn=8,
        meta=_MAP_META if meta is None else meta,
        input={"conversation_history": _HISTORY, "graph_state": graph_state or _map_graph_state()},
        observed_output="`str.format` の `{name}` は、渡した値に置き換わります。",
        turn_decision=decision,
        has_turn_decision=has_turn_decision,
    )


def _legacy_trace() -> ev.SourceTrace:
    return ev.SourceTrace(
        trace_id="2026-09-21-c7718f93__t4",
        turn=4,
        meta={"model": "gpt-4.1-nano", "prompt_version": "generate_question@v4", "captured_by": "capture"},
        input={
            "conversation_history": [
                {"role": "user", "content": "プロセス"},
                {"role": "assistant", "content": "知っていることを話してみてください。"},
                {"role": "user", "content": "動作中のプログラムのことです。"},
            ],
            "graph_state": {"topic": "プロセス", "covered_aspects": [], "turn_count": 1},
        },
        observed_output="o",
        turn_decision={
            "response_mode": "expand",
            "selected_aspect": "プロセス",
            "has_misconception": False,
            "error_summary": "",
            "covered_aspects": _LEGACY_COVERED,
        },
        has_turn_decision=True,
    )


def _map_result() -> dict[str, Any]:
    return {
        "messages": [AIMessage(content="再生成した応答")],
        "turn_count": 4,
        "should_generate_note": False,
        "depth_map": _DEPTH_MAP,
        "map_covered": _COVERED_AFTER,
        "turn_analysis": _ANALYSIS,
        "wrap_up_offered": False,
    }


def _legacy_result() -> dict[str, Any]:
    return {
        "messages": [AIMessage(content="旧経路の応答")],
        "turn_count": 2,
        "should_generate_note": False,
        "covered_aspects": _LEGACY_COVERED,
        "turn_analysis": None,
        "wrap_up_offered": True,
    }


def _map_generation(map_covered: list[dict[str, Any]]) -> ev.Generation:
    return ev.Generation(
        output="o",
        turn_analysis=_ANALYSIS,
        covered_aspects=[],
        turn_count=4,
        map_covered=map_covered,
        depth_map=_DEPTH_MAP,
    )


class TestReplayBlocker:
    def test_map_records_replay_in_both_modes(self) -> None:
        trace = _map_trace(_DECISION)

        assert ev.replay_blocker(trace, "full") is None
        assert ev.replay_blocker(trace, "pinned") is None

    def test_map_records_not_from_capture_are_still_rejected(self) -> None:
        meta = {key: value for key, value in _MAP_META.items() if key != "captured_by"}

        assert "capture" in (ev.replay_blocker(_map_trace(_DECISION, meta=meta), "full") or "")

    def test_pinned_map_replay_needs_a_turn_decision_key(self) -> None:
        trace = _map_trace(None, has_turn_decision=False)

        assert ev.replay_blocker(trace, "full") is None
        assert "turn_decision" in (ev.replay_blocker(trace, "pinned") or "")

    def test_a_null_turn_decision_still_allows_pinned_replay(self) -> None:
        assert ev.replay_blocker(_map_trace(None), "pinned") is None


class TestTraceRoute:
    def test_map_record(self) -> None:
        assert ev.trace_route(_map_trace(_DECISION)) == "map"

    def test_record_without_a_route_is_legacy(self) -> None:
        assert ev.trace_route(_legacy_trace()) == "legacy"


class TestToStateForMapRoute:
    def test_map_record_enters_the_map_route(self) -> None:
        state = ev.to_state(_map_trace(_DECISION))

        assert state["intake_complete"] is True
        assert state["depth_map"] == _DEPTH_MAP
        assert state["map_covered"] == _COVERED_BEFORE
        assert state["intake_message_count"] == 3
        assert state["learning_goal"] == "人に説明できるようになる"
        assert state["learning_source"] == "公式ドキュメント"
        assert state["prior_knowledge"] == "使ったことがある"
        assert state["turn_count"] == 3
        assert "covered_aspects" not in state

    def test_recorded_wrap_up_flag_is_kept(self) -> None:
        offered = ev.to_state(_map_trace(_DECISION, graph_state=_map_graph_state(wrap_up_offered=True)))
        pending = ev.to_state(_map_trace(_DECISION))

        assert offered["wrap_up_offered"] is True
        assert pending["wrap_up_offered"] is False

    def test_empty_intake_answers_are_left_unset(self) -> None:
        graph_state = _map_graph_state(learning_source=None, prior_knowledge=None)

        state = ev.to_state(_map_trace(_DECISION, graph_state=graph_state))

        assert "learning_source" not in state
        assert "prior_knowledge" not in state

    def test_dialogue_starts_after_the_intake_messages(self) -> None:
        state = ev.to_state(_map_trace(_DECISION))

        dialogue = state["messages"][state["intake_message_count"] :]

        assert [type(m) for m in dialogue] == [AIMessage, HumanMessage, AIMessage, HumanMessage]

    def test_legacy_record_stays_on_the_legacy_route(self) -> None:
        state = ev.to_state(_legacy_trace())

        assert "intake_complete" not in state
        assert "depth_map" not in state
        assert "map_covered" not in state

    def test_captured_map_record_round_trips(self) -> None:
        sources = ev.load_source_records()
        trace = ev.get_source_trace("2026-10-01-04d22b75__t8", sources)

        state = ev.to_state(trace)

        graph_state = sources["2026-10-01-04d22b75__t8"]["input"]["graph_state"]
        assert state["intake_complete"] is True
        assert state["depth_map"] == graph_state["depth_map"]
        assert state["intake_message_count"] == graph_state["intake_message_count"]
        assert len(state["messages"]) == trace.turn - 1


class TestToMapTurnPlan:
    def test_restores_the_saved_decision(self) -> None:
        plan = ev.to_map_turn_plan(_map_trace(_DECISION))

        assert plan.depth_map == _DEPTH_MAP
        assert plan.map_covered == _COVERED_AFTER
        assert plan.analysis is not None
        assert plan.analysis.response_mode == "reinforce"
        assert plan.analysis.selected_aspect_id == "値の指定と再利用"
        assert plan.analysis.has_misconception is True
        assert plan.analysis.error_summary == _ANALYSIS["error_summary"]
        assert plan.analysis.observations == []
        assert plan.wrap_up is False

    def test_restores_a_wrap_up_decision(self) -> None:
        decision = {**_DECISION, "has_misconception": False, "error_summary": "", "wrap_up": True}

        assert ev.to_map_turn_plan(_map_trace(decision)).wrap_up is True

    def test_a_null_decision_replays_without_an_analysis(self) -> None:
        plan = ev.to_map_turn_plan(_map_trace(None))

        assert plan.analysis is None
        assert plan.depth_map == _DEPTH_MAP
        assert plan.map_covered == _COVERED_BEFORE
        assert plan.wrap_up is False


class TestGenerateOutputRoute:
    async def test_full_replay_of_a_map_record_runs_the_map_nodes(self) -> None:
        prepare = AsyncMock(return_value=ev.to_map_turn_plan(_map_trace(_DECISION)))
        respond_map = AsyncMock(return_value=_map_result())

        with (
            patch("graph.nodes.learning_dialogue.prepare_map_turn", prepare),
            patch("graph.nodes.learning_dialogue.respond_map", respond_map),
        ):
            generation = await ev._generate_output_once(_map_trace(_DECISION), "full")

        assert respond_map.await_args_list[0].args[0]["intake_complete"] is True
        assert generation.output == "再生成した応答"
        assert generation.depth_map == _DEPTH_MAP
        assert generation.map_covered == _COVERED_AFTER
        assert generation.covered_aspects == []

    async def test_pinned_replay_of_a_map_record_injects_the_saved_plan(self) -> None:
        trace = _map_trace(_DECISION)
        respond_map = AsyncMock(return_value=_map_result())
        respond = AsyncMock(side_effect=AssertionError("旧経路の respond を呼んではいけない"))

        with patch("evals.eval.respond_map", respond_map), patch("evals.eval.respond", respond):
            generation = await ev._generate_output_once(trace, "pinned")

        assert respond_map.await_args_list[0].args[1] == ev.to_map_turn_plan(trace)
        assert generation.turn_decision() == _DECISION

    async def test_pinned_replay_of_a_legacy_record_keeps_the_legacy_node(self) -> None:
        respond = AsyncMock(return_value=_legacy_result())
        respond_map = AsyncMock(side_effect=AssertionError("地図の respond_map を呼んではいけない"))

        with patch("evals.eval.respond", respond), patch("evals.eval.respond_map", respond_map):
            generation = await ev._generate_output_once(_legacy_trace(), "pinned")

        assert generation.output == "旧経路の応答"
        assert generation.depth_map is None
        assert generation.map_covered == []

    async def test_full_replay_of_a_legacy_record_keeps_the_legacy_route(self) -> None:
        respond = AsyncMock(return_value=_legacy_result())
        respond_map = AsyncMock(side_effect=AssertionError("地図の respond_map を呼んではいけない"))

        with (
            patch("graph.nodes.learning_dialogue.prepare_turn", AsyncMock(return_value=TurnPlan())),
            patch("graph.nodes.learning_dialogue.respond", respond),
            patch("graph.nodes.learning_dialogue.respond_map", respond_map),
        ):
            generation = await ev._generate_output_once(_legacy_trace(), "full")

        assert generation.covered_aspects == _LEGACY_COVERED
        assert generation.depth_map is None


class TestGenerationMapFields:
    def test_map_turn_decision_has_the_capture_shape(self) -> None:
        decision = _map_generation(_COVERED_AFTER).turn_decision()

        assert decision is not None
        assert decision == _DECISION
        assert "covered_aspects" not in decision

    def test_legacy_turn_decision_is_unchanged(self) -> None:
        analysis = {"response_mode": "expand", "selected_aspect": "プロセス", "error_summary": ""}

        generation = ev.Generation("o", analysis, _LEGACY_COVERED, 3)

        assert generation.turn_decision() == {**analysis, "covered_aspects": _LEGACY_COVERED}

    def test_old_checkpoint_dict_without_map_keys_loads(self) -> None:
        cached: dict[str, Any] = {"output": "o", "turn_analysis": None, "covered_aspects": [], "turn_count": 3}

        generation = ev.Generation.from_checkpoint(cached)

        assert generation.map_covered == []
        assert generation.depth_map is None
        assert generation.turn_decision() is None

    def test_map_generation_round_trips_through_a_checkpoint(self) -> None:
        generation = _map_generation(_COVERED_AFTER)

        assert ev.Generation.from_checkpoint(asdict(generation)) == generation

    async def test_evaluate_instance_reuses_an_old_checkpointed_generation(self, tmp_path: Path) -> None:
        checkpoint = CheckpointStore(tmp_path)
        old: dict[str, Any] = {"output": "old", "turn_analysis": None, "covered_aspects": [], "turn_count": 3}
        checkpoint.save_generation("fm", "t1", 1, old)
        record = {"failure_mode": "fm", "assertions": []}
        instance: dict[str, Any] = {"source_trace_id": "t1", "human_verdicts": {}, "pass": None}
        generate = AsyncMock(side_effect=AssertionError("保存済みの生成を作り直してはいけない"))

        with (
            patch("evals.eval.generate_output", generate),
            patch("evals.eval.evaluate_output", AsyncMock(return_value=[])),
        ):
            result = await ev.evaluate_instance(
                record, instance, _legacy_trace(), MagicMock(), mode="regression", runs=1, checkpoint=checkpoint
            )

        generation = result.runs[0].generation
        assert generation is not None
        assert generation.output == "old"
        assert generation.depth_map is None


class TestMapCoverageStability:
    def _result(self, coverages: list[list[dict[str, Any]]]) -> ev.InstanceResult:
        result = ev.InstanceResult(failure_mode="uncorrected_misconception", source_trace_id="t", human_pass=True)
        for index, covered in enumerate(coverages, start=1):
            generation = _map_generation(covered)
            result.runs.append(ev.RunResult(run_index=index, output="o", outcomes=[], generation=generation))
        return result

    def test_map_runs_are_compared_by_aspect_id(self) -> None:
        rows = ev.coverage_stability([self._result([_COVERED_BEFORE, _COVERED_AFTER])])

        assert rows[0]["mean_jaccard"] == 0.5
        assert rows[0]["aspect_sets"] == [["式の評価方法"], ["値の指定と再利用", "式の評価方法"]]

    def test_report_keeps_the_map_coverage_of_each_run(self) -> None:
        result = self._result([_COVERED_AFTER])

        report = ev.build_report([result], [], mode="regression", runs=1, fingerprints={}, judge=llm_judge)

        run = report["records"][0]["runs"][0]
        assert run["map_covered"] == _COVERED_AFTER
        assert run["depth_map"] == _DEPTH_MAP
