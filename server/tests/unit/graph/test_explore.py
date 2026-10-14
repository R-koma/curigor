from graph.explore import merge_terms, ordered_aspects
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

    def test_keeps_a_term_without_a_reading(self) -> None:
        merged = merge_terms([], [ExploreTermDraft(term="計算量", meaning="手間の目安")])

        assert merged == [{"term": "計算量", "reading": "", "meaning": "手間の目安"}]


class TestAspectOrder:
    def test_core_aspects_come_first_in_map_order(self) -> None:
        assert [a["id"] for a in ordered_aspects(MAP)] == ["比較", "計算量", "前提"]
