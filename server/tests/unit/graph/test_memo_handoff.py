from graph.memo_handoff import MAX_MEMO_TERMS, memo_kickoff, memo_terms_from_glossary
from graph.state import DepthMapAspectState, DepthMapState


def _aspect(aspect_id: str, name: str, *, is_core: bool) -> DepthMapAspectState:
    return {
        "id": aspect_id,
        "name": name,
        "is_core": is_core,
        "defined_question": "d",
        "reasoned_question": "r",
        "applied_question": "a",
    }


class TestMemoTermsFromGlossary:
    def test_keeps_only_the_term_and_its_reading(self) -> None:
        glossary = [{"term": "計算量", "reading": "けいさんりょう", "meaning": "処理にかかる手間の目安"}]

        assert memo_terms_from_glossary(glossary) == [{"term": "計算量", "reading": "けいさんりょう"}]

    def test_drops_blank_terms_and_tolerates_missing_fields(self) -> None:
        glossary = [{"term": "  ", "reading": "x"}, {"term": "添字"}, {"reading": "y"}]

        assert memo_terms_from_glossary(glossary) == [{"term": "添字", "reading": ""}]

    def test_caps_the_number_of_terms(self) -> None:
        glossary = [{"term": f"用語{i}", "reading": ""} for i in range(MAX_MEMO_TERMS + 5)]

        assert len(memo_terms_from_glossary(glossary)) == MAX_MEMO_TERMS


class TestMemoKickoff:
    def test_asks_to_explain_starting_from_the_first_core_aspect(self) -> None:
        depth_map: DepthMapState = {
            "topic": "二分探索",
            "aspects": [_aspect("a", "並んでいる前提", is_core=False), _aspect("b", "真ん中との比較", is_core=True)],
        }

        text = memo_kickoff("二分探索", depth_map)

        assert "「二分探索」" in text
        assert "「真ん中との比較」から" in text
        assert "並んでいる前提" not in text

    def test_omits_the_aspect_when_the_map_is_empty(self) -> None:
        text = memo_kickoff("二分探索", {"topic": "二分探索", "aspects": []})

        assert "「二分探索」" in text
        assert "から、" not in text
