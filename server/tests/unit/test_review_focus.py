from services.review_focus import ReviewFocus, build_review_focus

MAP = {
    "root": "二分探索",
    "aspects": [
        {"name": "計算量", "summary": "", "coverage": "covered", "children": []},
        {"name": "前提条件", "summary": "", "coverage": "partial", "children": []},
    ],
}
FEEDBACK = {"improvements": "計算量の見積もり\nソート済みの前提\n用語の使い分け"}


def test_keeps_every_improvement() -> None:
    assert build_review_focus(FEEDBACK, MAP) == ReviewFocus(FEEDBACK["improvements"], [])


def test_note_without_aspect_map_keeps_every_improvement() -> None:
    assert build_review_focus(FEEDBACK, None, memo_aspect_ids=["a1"]) == ReviewFocus(FEEDBACK["improvements"], [])


def test_no_feedback_has_no_improvements() -> None:
    assert build_review_focus(None, MAP) == ReviewFocus(None, [])


def test_blank_improvements_become_none() -> None:
    assert build_review_focus({"improvements": "  "}, None) == ReviewFocus(None, [])


def test_priority_aspects_are_memo_aspects_in_map_order() -> None:
    assert build_review_focus(FEEDBACK, MAP, memo_aspect_ids=["a2", "zz"]).priority_aspects == ["前提条件"]
    assert build_review_focus(FEEDBACK, MAP, memo_aspect_ids=["a2", "a1"]).priority_aspects == ["計算量", "前提条件"]
