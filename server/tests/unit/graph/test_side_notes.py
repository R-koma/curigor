from uuid import uuid4

from graph.nodes._explore_llm import SideQuestionDigest
from graph.output_schemas import ExploreTermDraft
from graph.side_notes import (
    SIDE_SECTION_HEADING,
    build_side_section,
    first_questions,
    insert_side_section,
    side_items,
)


def test_side_items_follow_thread_order_and_skip_missing() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    ordered = [{"id": a}, {"id": b}, {"id": c}]
    digests = {
        c: SideQuestionDigest(term=None, question="なぜ索引で速くなるのか", answer="全件を読まずに済むため"),
        a: SideQuestionDigest(
            term=ExploreTermDraft(term="索引", reading="", meaning="探す場所を引く表"), question="", answer=""
        ),
    }

    assert side_items(ordered, digests) == [
        ("「索引」とは何か", "探す場所を引く表"),
        ("なぜ索引で速くなるのか", "全件を読まずに済むため"),
    ]


def test_side_items_put_the_term_before_the_question_of_one_thread() -> None:
    a = uuid4()
    digests = {
        a: SideQuestionDigest(
            term=ExploreTermDraft(term="B木", reading="", meaning="枝の多い木"), question="なぜ速い？", answer="浅い"
        )
    }

    assert side_items([{"id": a}], digests) == [("「B木」とは何か", "枝の多い木"), ("なぜ速い？", "浅い")]


def test_side_items_skip_a_question_without_an_answer() -> None:
    a = uuid4()
    digests = {a: SideQuestionDigest(term=None, question="なぜ？", answer="")}

    assert side_items([{"id": a}], digests) == []


def test_build_side_section_is_single_line_per_item() -> None:
    section = build_side_section([("なぜ\n速い？", "全件を\n\n読まない")])

    assert section == "## わからなかったこと\n- **なぜ 速い？**\n  - 全件を 読まない"
    assert section.startswith(SIDE_SECTION_HEADING)


def test_build_side_section_is_empty_without_items() -> None:
    assert build_side_section([]) == ""


def test_insert_goes_before_the_ambiguous_callout() -> None:
    content = "リード\n\n## 学んだこと\n- a\n\n> **まだ曖昧な点**\n> - b"

    result = insert_side_section(content, "## わからなかったこと\n- **Q**\n  - A")

    assert result == (
        "リード\n\n## 学んだこと\n- a\n\n## わからなかったこと\n- **Q**\n  - A\n\n> **まだ曖昧な点**\n> - b"
    )


def test_insert_appends_when_there_is_no_callout() -> None:
    assert insert_side_section("リード\n", "S") == "リード\n\nS"


def test_insert_is_a_no_op_for_an_empty_section() -> None:
    assert insert_side_section("リード", "") == "リード"


def test_first_questions_take_the_first_user_message_of_each_thread() -> None:
    threads = [
        {"messages": [{"role": "user", "content": "索引とは？"}, {"role": "assistant", "content": "表"}]},
        {"messages": [{"role": "assistant", "content": "x"}]},
        {"messages": [{"role": "user", "content": " なぜ？ "}, {"role": "user", "content": "続き"}]},
    ]

    assert first_questions(threads) == ["索引とは？", "なぜ？"]
