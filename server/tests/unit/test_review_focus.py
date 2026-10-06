import json

from services.review_focus import ReviewFocus, build_review_focus

MAP = {
    "root": "二分探索",
    "aspects": [
        {"name": "計算量", "summary": "", "coverage": "covered", "children": []},
        {"name": "前提条件", "summary": "", "coverage": "partial", "children": []},
    ],
}
ITEMS = [
    {"text": "計算量の見積もり", "aspect_id": "a1"},
    {"text": "ソート済みの前提", "aspect_id": "a2"},
    {"text": "用語の使い分け", "aspect_id": None},
]
FEEDBACK = {
    "improvements": "計算量の見積もり\nソート済みの前提\n用語の使い分け",
    "improvement_items": json.dumps(ITEMS),
}
ALL = FEEDBACK["improvements"]


def test_without_selection_keeps_every_improvement() -> None:
    assert build_review_focus(FEEDBACK, MAP, None) == ReviewFocus(ALL, [])


def test_selection_keeps_selected_and_unlinked_improvements() -> None:
    assert build_review_focus(FEEDBACK, MAP, ["a2"]) == ReviewFocus("ソート済みの前提\n用語の使い分け", ["前提条件"])


def test_focus_names_follow_map_order_and_drop_unknown_ids() -> None:
    assert build_review_focus(FEEDBACK, MAP, ["a2", "a9", "a1"]).focus_aspects == ["計算量", "前提条件"]


def test_only_unknown_ids_behave_like_an_empty_selection() -> None:
    assert build_review_focus(FEEDBACK, MAP, ["a9"]) == ReviewFocus("用語の使い分け", [])


def test_empty_selection_keeps_only_unlinked_improvements() -> None:
    assert build_review_focus(FEEDBACK, MAP, []) == ReviewFocus("用語の使い分け", [])


def test_legacy_feedback_without_items_keeps_every_improvement() -> None:
    legacy = {"improvements": "古い改善点", "improvement_items": None}
    assert build_review_focus(legacy, MAP, ["a1"]) == ReviewFocus("古い改善点", ["計算量"])


def test_note_without_aspect_map_keeps_every_improvement_and_no_focus() -> None:
    assert build_review_focus(FEEDBACK, None, ["a1"]) == ReviewFocus(ALL, [])


def test_no_feedback_still_focuses_the_selected_aspects() -> None:
    assert build_review_focus(None, MAP, ["a1"]) == ReviewFocus(None, ["計算量"])


def test_blank_improvements_become_none() -> None:
    assert build_review_focus({"improvements": "  ", "improvement_items": None}, None, None) == ReviewFocus(None, [])


def test_items_given_as_a_json_string_or_a_list_are_both_read() -> None:
    as_list = {"improvements": ALL, "improvement_items": ITEMS}
    assert build_review_focus(as_list, MAP, ["a1"]) == build_review_focus(FEEDBACK, MAP, ["a1"])


def test_broken_items_json_keeps_every_improvement() -> None:
    broken = {"improvements": "古い", "improvement_items": "{broken"}
    assert build_review_focus(broken, MAP, ["a1"]) == ReviewFocus("古い", ["計算量"])
