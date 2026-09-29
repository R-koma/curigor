from graph.depth_map import (
    build_depth_map,
    depth_map_progress,
    format_map_coverage,
    merge_map_coverage,
    next_stage,
    question_for,
    resolve_aspect,
    slugify_aspect_id,
)
from graph.output_schemas import DepthMapAspectDraft, MapAspectObservation
from graph.state import MapAspectProgress


def _draft(name: str, is_core: bool) -> DepthMapAspectDraft:
    return DepthMapAspectDraft(
        name=name,
        is_core=is_core,
        defined_question=f"{name}を定義できるか",
        reasoned_question=f"{name}のなぜ・仕組み",
        applied_question=f"{name}の応用",
    )


class TestSlugifyAspectId:
    def test_slugifies_japanese_name(self) -> None:
        assert slugify_aspect_id("システムコール", []) != ""

    def test_avoids_collision_with_existing_ids(self) -> None:
        first = slugify_aspect_id("キュー", [])
        second = slugify_aspect_id("キュー", [first])
        assert first != second


class TestBuildDepthMap:
    def test_caps_core_aspects_at_four(self) -> None:
        drafts = [_draft(f"観点{i}", True) for i in range(6)]
        depth_map = build_depth_map("トピック", drafts)
        core = [a for a in depth_map["aspects"] if a["is_core"]]
        assert len(core) == 4
        assert [a["name"] for a in core] == ["観点0", "観点1", "観点2", "観点3"]

    def test_promotes_first_aspect_to_core_when_none_marked(self) -> None:
        drafts = [_draft("観点A", False), _draft("観点B", False)]
        depth_map = build_depth_map("トピック", drafts)
        assert depth_map["aspects"][0]["is_core"] is True

    def test_assigns_stable_unique_ids(self) -> None:
        depth_map = build_depth_map("トピック", [_draft("キュー", True), _draft("キュー", False)])
        ids = [a["id"] for a in depth_map["aspects"]]
        assert len(ids) == len(set(ids))


class TestQuestionForAndNextStage:
    def test_mentioned_and_defined_use_defined_question(self) -> None:
        aspect = build_depth_map("t", [_draft("キュー", True)])["aspects"][0]
        assert question_for(aspect, "mentioned") == question_for(aspect, "defined") == "キューを定義できるか"

    def test_reasoned_and_applied_use_their_own_question(self) -> None:
        aspect = build_depth_map("t", [_draft("キュー", True)])["aspects"][0]
        assert question_for(aspect, "reasoned") == "キューのなぜ・仕組み"
        assert question_for(aspect, "applied") == "キューの応用"

    def test_next_stage_progression(self) -> None:
        assert next_stage(None) == "mentioned"
        assert next_stage("mentioned") == "defined"
        assert next_stage("defined") == "reasoned"
        assert next_stage("reasoned") == "applied"
        assert next_stage("applied") == "applied"


class TestResolveAspect:
    def test_matches_by_id_or_name(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True)])
        aspect_id = depth_map["aspects"][0]["id"]
        resolved_by_id, unchanged = resolve_aspect(aspect_id, depth_map)
        resolved_by_name, _ = resolve_aspect("キュー", depth_map)
        assert resolved_by_id == resolved_by_name == aspect_id
        assert unchanged == depth_map

    def test_unknown_reference_adds_a_new_non_core_aspect(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True)])
        new_id, updated = resolve_aspect("スタック", depth_map)
        added = next(a for a in updated["aspects"] if a["id"] == new_id)
        assert added["name"] == "スタック"
        assert added["is_core"] is False
        assert len(updated["aspects"]) == 2


class TestMergeMapCoverage:
    def test_upgrade_only(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True)])
        aspect_id = depth_map["aspects"][0]["id"]
        existing: list[MapAspectProgress] = [{"aspect_id": aspect_id, "reached_stage": "reasoned"}]
        observations = [MapAspectObservation(aspect_id=aspect_id, reached_stage="defined")]
        merged, unchanged_map = merge_map_coverage(existing, observations, depth_map)
        assert merged == [{"aspect_id": aspect_id, "reached_stage": "reasoned"}]
        assert unchanged_map == depth_map

    def test_unknown_observation_grows_the_map_and_is_recorded(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True)])
        observations = [MapAspectObservation(aspect_id="スタック", reached_stage="defined")]
        merged, updated_map = merge_map_coverage([], observations, depth_map)
        assert len(updated_map["aspects"]) == 2
        new_id = updated_map["aspects"][1]["id"]
        assert merged == [{"aspect_id": new_id, "reached_stage": "defined"}]


class TestDepthMapProgress:
    def test_counts_only_core_aspects_at_or_beyond_reasoned(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True), _draft("スタック", True), _draft("木", False)])
        ids = [a["id"] for a in depth_map["aspects"]]
        covered: list[MapAspectProgress] = [
            {"aspect_id": ids[0], "reached_stage": "reasoned"},
            {"aspect_id": ids[1], "reached_stage": "defined"},
            {"aspect_id": ids[2], "reached_stage": "applied"},
        ]
        progress = depth_map_progress(covered, depth_map)
        assert progress.reached_aspects == ("キュー",)
        assert progress.target_count == 2
        assert progress.is_complete is False

    def test_is_complete_when_all_core_aspects_reach_reasoned(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True), _draft("スタック", True)])
        ids = [a["id"] for a in depth_map["aspects"]]
        covered: list[MapAspectProgress] = [
            {"aspect_id": ids[0], "reached_stage": "reasoned"},
            {"aspect_id": ids[1], "reached_stage": "applied"},
        ]
        assert depth_map_progress(covered, depth_map).is_complete is True

    def test_non_core_extension_aspects_do_not_affect_completion(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True)])
        ids = [a["id"] for a in depth_map["aspects"]]
        _, grown_map = resolve_aspect("スタック", depth_map)
        covered: list[MapAspectProgress] = [{"aspect_id": ids[0], "reached_stage": "reasoned"}]
        progress = depth_map_progress(covered, grown_map)
        assert progress.target_count == 1
        assert progress.is_complete is True


class TestFormatMapCoverage:
    def test_empty_returns_empty_string(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True)])
        assert format_map_coverage([], depth_map) == ""

    def test_renders_name_and_stage_label(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True)])
        aspect_id = depth_map["aspects"][0]["id"]
        covered: list[MapAspectProgress] = [{"aspect_id": aspect_id, "reached_stage": "defined"}]
        assert format_map_coverage(covered, depth_map) == "- キュー: defined（定義済み）"
