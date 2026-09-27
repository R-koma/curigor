from graph.coverage import WRAP_UP_MIN_ASPECTS, coverage_progress, format_covered_aspects, merge_coverage
from graph.output_schemas import AspectObservation
from graph.state import CoveredAspect


class TestMergeCoverage:
    def test_adds_new_aspects_preserving_order(self) -> None:
        existing: list[CoveredAspect] = [{"aspect": "信頼性", "reached_depth": "defined"}]
        observations = [
            AspectObservation(aspect="スケーラビリティ", reached_depth="mentioned"),
            AspectObservation(aspect="メンテナンス性", reached_depth="defined"),
        ]
        assert merge_coverage(existing, observations) == [
            {"aspect": "信頼性", "reached_depth": "defined"},
            {"aspect": "スケーラビリティ", "reached_depth": "mentioned"},
            {"aspect": "メンテナンス性", "reached_depth": "defined"},
        ]

    def test_promotes_depth(self) -> None:
        existing: list[CoveredAspect] = [{"aspect": "信頼性", "reached_depth": "defined"}]
        observations = [AspectObservation(aspect="信頼性", reached_depth="applied")]
        assert merge_coverage(existing, observations) == [{"aspect": "信頼性", "reached_depth": "applied"}]

    def test_never_demotes_depth(self) -> None:
        existing: list[CoveredAspect] = [{"aspect": "信頼性", "reached_depth": "exemplified"}]
        observations = [AspectObservation(aspect="信頼性", reached_depth="mentioned")]
        assert merge_coverage(existing, observations) == [{"aspect": "信頼性", "reached_depth": "exemplified"}]

    def test_empty_inputs(self) -> None:
        assert merge_coverage([], []) == []


class TestFormatCoveredAspects:
    def test_empty_returns_empty_string(self) -> None:
        assert format_covered_aspects([]) == ""

    def test_renders_depth_with_japanese_label(self) -> None:
        covered: list[CoveredAspect] = [{"aspect": "計算量", "reached_depth": "defined"}]
        assert format_covered_aspects(covered) == "- 計算量: defined（定義済み）"


class TestCoverageProgress:
    def test_counts_only_aspects_at_or_beyond_exemplified(self) -> None:
        covered: list[CoveredAspect] = [
            {"aspect": "前提条件", "reached_depth": "exemplified"},
            {"aspect": "計算量", "reached_depth": "defined"},
            {"aspect": "境界条件", "reached_depth": "applied"},
            {"aspect": "用途", "reached_depth": "mentioned"},
        ]
        progress = coverage_progress(covered, None)
        assert progress.reached_aspects == ("前提条件", "境界条件")
        assert progress.target_count == WRAP_UP_MIN_ASPECTS
        assert progress.is_complete is False

    def test_completes_at_the_minimum_count_without_focus_aspects(self) -> None:
        covered: list[CoveredAspect] = [
            {"aspect": "前提条件", "reached_depth": "exemplified"},
            {"aspect": "計算量", "reached_depth": "exemplified"},
            {"aspect": "境界条件", "reached_depth": "applied"},
        ]
        assert coverage_progress(covered, None).is_complete is True
        assert coverage_progress(covered, []).is_complete is True

    def test_focus_aspects_require_every_listed_aspect(self) -> None:
        covered: list[CoveredAspect] = [
            {"aspect": "前提条件", "reached_depth": "exemplified"},
            {"aspect": "計算量", "reached_depth": "exemplified"},
            {"aspect": "境界条件", "reached_depth": "exemplified"},
            {"aspect": "用途", "reached_depth": "defined"},
        ]
        progress = coverage_progress(covered, ["用途", "計算量"])
        assert progress.reached_aspects == ("計算量",)
        assert progress.target_count == 2
        assert progress.is_complete is False

    def test_focus_aspects_complete_when_all_reached(self) -> None:
        covered: list[CoveredAspect] = [
            {"aspect": "計算量", "reached_depth": "applied"},
            {"aspect": "用途", "reached_depth": "exemplified"},
        ]
        progress = coverage_progress(covered, ["用途", "計算量"])
        assert progress.reached_aspects == ("用途", "計算量")
        assert progress.is_complete is True

    def test_empty_coverage(self) -> None:
        progress = coverage_progress([], None)
        assert progress.reached_aspects == ()
        assert progress.is_complete is False
