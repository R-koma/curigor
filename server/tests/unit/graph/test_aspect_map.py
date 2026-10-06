import json

from graph.aspect_map import (
    aspect_names_by_id,
    feedback_insert_fields,
    iter_aspects,
    link_improvements,
    parse_aspect_map,
    with_aspect_ids,
)
from graph.output_schemas import FeedbackOutput, ImprovementPoint

MAP = {
    "root": "二分探索",
    "aspects": [
        {
            "name": "計算量",
            "summary": "",
            "coverage": "covered",
            "children": [
                {
                    "name": "最悪計算量",
                    "summary": "",
                    "coverage": "partial",
                    "children": [{"name": "対数", "summary": "", "coverage": "uncovered", "children": []}],
                },
            ],
        },
        {"name": "前提条件", "summary": "", "coverage": "partial", "children": []},
    ],
}


class TestWithAspectIds:
    def test_assigns_positional_ids_depth_first(self) -> None:
        result = with_aspect_ids(MAP)
        assert result["aspects"][0]["id"] == "a1"
        assert result["aspects"][0]["children"][0]["id"] == "a1-1"
        assert result["aspects"][0]["children"][0]["children"][0]["id"] == "a1-1-1"
        assert result["aspects"][1]["id"] == "a2"

    def test_does_not_mutate_input(self) -> None:
        with_aspect_ids(MAP)
        assert json.dumps(MAP).count('"id"') == 0

    def test_overwrites_stale_ids(self) -> None:
        stale = {"root": "x", "aspects": [{"id": "zz", "name": "n", "summary": "", "coverage": "covered"}]}
        assert with_aspect_ids(stale)["aspects"][0]["id"] == "a1"


class TestIterAspects:
    def test_yields_id_name_depth_in_saved_order(self) -> None:
        assert [tuple(r) for r in iter_aspects(MAP)] == [
            ("a1", "計算量", 0),
            ("a1-1", "最悪計算量", 1),
            ("a1-1-1", "対数", 2),
            ("a2", "前提条件", 0),
        ]

    def test_empty_aspects(self) -> None:
        assert list(iter_aspects({"root": "x", "aspects": []})) == []


class TestParseAspectMap:
    def test_parses_json_string(self) -> None:
        assert parse_aspect_map(json.dumps(MAP)) == MAP

    def test_accepts_dict(self) -> None:
        assert parse_aspect_map(MAP) == MAP

    def test_none_and_broken_values(self) -> None:
        assert parse_aspect_map(None) is None
        assert parse_aspect_map("{broken") is None
        assert parse_aspect_map({"root": "x"}) is None


def test_aspect_names_by_id() -> None:
    assert aspect_names_by_id(MAP)["a1-1"] == "最悪計算量"
    assert aspect_names_by_id(None) == {}


class TestLinkImprovements:
    def test_keeps_known_ids_and_drops_unknown(self) -> None:
        points = [
            ImprovementPoint(text="最悪計算量が曖昧", aspect_id="a1-1"),
            ImprovementPoint(text="名前で返った", aspect_id="計算量"),
            ImprovementPoint(text="存在しない", aspect_id="a9"),
            ImprovementPoint(text="空", aspect_id=""),
            ImprovementPoint(text="空白入り", aspect_id=" a2 "),
        ]
        assert [item["aspect_id"] for item in link_improvements(points, MAP)] == ["a1-1", None, None, None, "a2"]

    def test_without_aspect_map_links_nothing(self) -> None:
        points = [ImprovementPoint(text="t", aspect_id="a1")]
        assert link_improvements(points, None) == [{"text": "t", "aspect_id": None}]

    def test_collapses_newlines_and_drops_blank_items(self) -> None:
        points = [ImprovementPoint(text="一行目\n二行目", aspect_id="a1"), ImprovementPoint(text="  ", aspect_id="a2")]
        assert link_improvements(points, MAP) == [{"text": "一行目 二行目", "aspect_id": "a1"}]

    def test_strips_leading_bullet_markers_and_drops_marker_only_items(self) -> None:
        points = [
            ImprovementPoint(text="・計算量を見直す", aspect_id="a1"),
            ImprovementPoint(text="- 前提を確認", aspect_id="a2"),
            ImprovementPoint(text="・", aspect_id="a1"),
        ]
        assert link_improvements(points, MAP) == [
            {"text": "計算量を見直す", "aspect_id": "a1"},
            {"text": "前提を確認", "aspect_id": "a2"},
        ]


def test_feedback_insert_fields_keeps_lines_and_items_aligned() -> None:
    feedback = FeedbackOutput(
        understanding_level="medium",
        strength=["良い"],
        improvement_points=[ImprovementPoint(text="A\nB", aspect_id="a1"), ImprovementPoint(text="C")],
    )
    fields = feedback_insert_fields(feedback, MAP)
    assert fields["improvements"] == "A B\nC"
    assert json.loads(fields["improvement_items"]) == [
        {"text": "A B", "aspect_id": "a1"},
        {"text": "C", "aspect_id": None},
    ]
    assert fields["strength"] == "良い"
