import json

from graph.aspect_map import aspect_names_by_id, iter_aspects, parse_aspect_map, with_aspect_ids

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
