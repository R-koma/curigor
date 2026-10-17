from graph.explore import build_overview, merge_terms, ordered_aspects
from graph.output_schemas import ExploreMemoAspect, ExploreMemoOrganization, ExploreTermDraft
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


OVERVIEW_ASPECTS = [_aspect("比較", "真ん中との比較", is_core=True), _aspect("前提", "並んでいる前提", is_core=False)]
OVERVIEW_MAP_ASPECTS = [OVERVIEW_ASPECTS[1], OVERVIEW_ASPECTS[0]]


def _organization(*aspects: ExploreMemoAspect) -> ExploreMemoOrganization:
    return ExploreMemoOrganization(summary="全体", aspects=list(aspects))


class TestBuildOverview:
    def test_overview_keeps_core_first_and_copies_summaries_and_indices(self) -> None:
        organization = _organization(
            ExploreMemoAspect(aspect_id="比較", summary="真ん中と比べる", question_indices=[0], term_indices=[1]),
            ExploreMemoAspect(aspect_id="前提", summary="", question_indices=[1]),
        )

        overview = build_overview(OVERVIEW_MAP_ASPECTS, organization, question_count=2, term_count=2)

        assert overview == [
            {
                "aspect_id": "比較",
                "name": "真ん中との比較",
                "summary": "真ん中と比べる",
                "is_core": True,
                "question_indices": [0],
                "term_indices": [1],
            },
            {
                "aspect_id": "前提",
                "name": "並んでいる前提",
                "summary": "",
                "is_core": False,
                "question_indices": [1],
                "term_indices": [],
            },
        ]

    def test_overview_drops_indices_out_of_range(self) -> None:
        organization = _organization(
            ExploreMemoAspect(aspect_id="比較", summary="", question_indices=[0, 3, -1], term_indices=[5])
        )

        overview = build_overview(OVERVIEW_ASPECTS, organization, question_count=1, term_count=1)

        assert overview[0]["question_indices"] == [0]
        assert overview[0]["term_indices"] == []

    def test_overview_gives_a_repeated_index_to_the_first_aspect_only(self) -> None:
        organization = _organization(
            ExploreMemoAspect(aspect_id="前提", summary="", question_indices=[0], term_indices=[0]),
            ExploreMemoAspect(aspect_id="比較", summary="", question_indices=[0], term_indices=[0]),
        )

        overview = build_overview(OVERVIEW_ASPECTS, organization, question_count=1, term_count=1)

        assert overview[0]["question_indices"] == [0]
        assert overview[0]["term_indices"] == [0]
        assert overview[1]["question_indices"] == []
        assert overview[1]["term_indices"] == []

    def test_overview_ignores_unknown_aspect_ids_and_keeps_missing_aspects_empty(self) -> None:
        organization = _organization(ExploreMemoAspect(aspect_id="無い", summary="x", question_indices=[0]))

        overview = build_overview(OVERVIEW_ASPECTS, organization, question_count=1, term_count=1)

        assert [(o["summary"], o["question_indices"], o["term_indices"]) for o in overview] == [
            ("", [], []),
            ("", [], []),
        ]

    def test_overview_without_organization_has_empty_summaries_and_indices(self) -> None:
        overview = build_overview(OVERVIEW_ASPECTS, None, question_count=1, term_count=1)

        assert [(o["summary"], o["question_indices"], o["term_indices"]) for o in overview] == [
            ("", [], []),
            ("", [], []),
        ]
