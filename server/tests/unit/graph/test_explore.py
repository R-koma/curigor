from graph.explore import (
    all_core_explained,
    known_aspect_id,
    merge_terms,
    next_aspect_id,
    ordered_aspects,
    overview_aspects,
    overview_text,
)
from graph.output_schemas import ExploreTermDraft
from graph.state import DepthMapAspectState, DepthMapState, ExploreTerm


def _aspect(aspect_id: str, name: str, *, is_core: bool) -> DepthMapAspectState:
    return {
        "id": aspect_id,
        "name": name,
        "is_core": is_core,
        "defined_question": f"{name}とは",
        "reasoned_question": f"なぜ{name}か",
        "applied_question": f"{name}をどう使うか",
    }


MAP: DepthMapState = {
    "topic": "二分探索",
    "aspects": [
        _aspect("前提", "並んでいる前提", is_core=False),
        _aspect("比較", "真ん中との比較", is_core=True),
        _aspect("計算量", "計算量", is_core=True),
    ],
}


class TestMergeTerms:
    def test_keeps_the_first_spelling_when_width_or_case_differs(self) -> None:
        existing: list[ExploreTerm] = [{"term": "API", "reading": "えーぴーあい", "meaning": "窓口"}]
        drafts = [
            ExploreTermDraft(term="ＡＰＩ", reading="えーぴーあい", meaning="別の説明"),
            ExploreTermDraft(term="api", reading="えーぴーあい", meaning="別の説明"),
            ExploreTermDraft(term="計算量", reading="けいさんりょう", meaning="手間の目安"),
        ]

        merged = merge_terms(existing, drafts)

        assert [t["term"] for t in merged] == ["API", "計算量"]
        assert merged[0]["meaning"] == "窓口"

    def test_drops_blank_terms(self) -> None:
        assert merge_terms([], [ExploreTermDraft(term="  ", reading="", meaning="")]) == []


class TestAspectOrder:
    def test_core_aspects_come_first_in_map_order(self) -> None:
        assert [a["id"] for a in ordered_aspects(MAP)] == ["比較", "計算量", "前提"]

    def test_next_aspect_skips_explained_ones(self) -> None:
        assert next_aspect_id(MAP, []) == "比較"
        assert next_aspect_id(MAP, ["比較"]) == "計算量"
        assert next_aspect_id(MAP, ["比較", "計算量"]) == "前提"
        assert next_aspect_id(MAP, ["比較", "計算量", "前提"]) is None


class TestKnownAspectId:
    def test_matches_id_or_name(self) -> None:
        assert known_aspect_id("比較", MAP) == "比較"
        assert known_aspect_id("真ん中との比較", MAP) == "比較"
        assert known_aspect_id(" 計算量 ", MAP) == "計算量"

    def test_unknown_reference_is_not_added_to_the_map(self) -> None:
        assert known_aspect_id("ハッシュ表", MAP) is None
        assert len(MAP["aspects"]) == 3

    def test_blank_reference_is_unknown(self) -> None:
        assert known_aspect_id("", MAP) is None


class TestAllCoreExplained:
    def test_needs_every_core_aspect(self) -> None:
        assert all_core_explained(MAP, ["比較"]) is False
        assert all_core_explained(MAP, ["比較", "計算量"]) is True


class TestOverview:
    def test_marks_explained_aspects_and_fills_missing_summaries(self) -> None:
        aspects = overview_aspects(MAP, {"比較": "真ん中と比べて半分を捨てる"}, ["比較"])

        assert aspects[0] == {
            "aspect_id": "比較",
            "name": "真ん中との比較",
            "summary": "真ん中と比べて半分を捨てる",
            "is_core": True,
            "explained": True,
        }
        assert aspects[1]["summary"] == ""
        assert aspects[1]["explained"] is False

    def test_text_lists_aspects_in_order_and_asks_where_to_start(self) -> None:
        text = overview_text("二分探索", overview_aspects(MAP, {"比較": "半分を捨てる"}, []))

        assert "「二分探索」" in text
        assert "1. 真ん中との比較: 半分を捨てる" in text
        assert "2. 計算量\n" in text
        assert text.rstrip().endswith("どこから始めますか？迷ったら「最初から」と送ってください。")
