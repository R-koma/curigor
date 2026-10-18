from typing import Any

from graph.prompts.review_plan import REVIEW_PLAN_PROMPT_FINGERPRINT, build_review_plan_prompt
from graph.review_plan import CarryoverPoint, ReviewResult

ASPECT_MAP: dict[str, Any] = {
    "root": "T",
    "aspects": [
        {
            "name": "再送制御",
            "summary": "失ったパケットを送り直す",
            "coverage": "partial",
            "children": [{"name": "タイムアウト", "summary": "待ち時間で判断する", "coverage": "uncovered"}],
        },
        {"name": "輻輳制御", "summary": "送る量を絞る", "coverage": "covered"},
    ],
}


def _prompt(
    *,
    aspect_map: dict[str, Any] | None = None,
    improvements: list[dict[str, Any]] | None = None,
    carryover: list[CarryoverPoint] | None = None,
    previous_questions: list[str] | None = None,
    explained: list[ReviewResult] | None = None,
    review_count: int = 0,
) -> str:
    return build_review_plan_prompt(
        topic="TCP",
        summary="要約",
        content="## 学んだこと\n- 本文",
        aspect_map=aspect_map,
        improvements=improvements or [],
        carryover=carryover or [],
        previous_questions=previous_questions or [],
        explained=explained or [],
        review_count=review_count,
    )


def test_prompt_lists_carryover_keys_and_previous_questions() -> None:
    text = _prompt(
        carryover=[
            {"key": "c1", "point": "再送の仕組み", "question": "再送はどう動く？", "aspect_id": "a1", "expected": []}
        ],
        previous_questions=["輻輳制御が要る理由を説明してください"],
        review_count=2,
    )

    assert "c1: 再送の仕組み" in text
    assert "再送はどう動く？" in text
    assert "輻輳制御が要る理由を説明してください" in text


def test_prompt_shows_aspect_ids_with_coverage_and_summary() -> None:
    text = _prompt(aspect_map=ASPECT_MAP)

    assert "- a1: 再送制御（partial）— 失ったパケットを送り直す" in text
    assert "  - a1-1: タイムアウト（uncovered）— 待ち時間で判断する" in text
    assert "- a2: 輻輳制御（covered）— 送る量を絞る" in text


def test_prompt_lists_improvements_with_their_aspect() -> None:
    text = _prompt(
        improvements=[
            {"text": "タイムアウトの決め方が曖昧", "aspect_id": "a1-1"},
            {"text": "全体", "aspect_id": None},
        ],
    )

    assert "- タイムアウトの決め方が曖昧（観点: a1-1）" in text
    assert "- 全体\n" in text


def test_prompt_marks_empty_inputs() -> None:
    text = _prompt()

    assert "{" not in text.replace("{{", "")
    assert text.count("（なし）") >= 3


def test_prompt_depth_stage_changes_with_review_count() -> None:
    first = _prompt(review_count=0)
    later = _prompt(review_count=2)
    many = _prompt(review_count=5)

    assert "定義と仕組み" in first
    assert "半分以上" in later
    assert first != later != many
    assert "完了した復習: 5 回" in many


def test_fingerprint_is_short_hex() -> None:
    assert len(REVIEW_PLAN_PROMPT_FINGERPRINT) == 12
    int(REVIEW_PLAN_PROMPT_FINGERPRINT, 16)


def test_prompt_separates_summary_when_coverage_is_missing() -> None:
    text = _prompt(aspect_map={"aspects": [{"name": "再送制御", "summary": "送り直す"}]})

    assert "- a1: 再送制御 — 送り直す" in text


def test_prompt_labels_the_carryover_question_as_prepared() -> None:
    text = _prompt(carryover=[{"key": "c1", "point": "A", "question": "Q", "aspect_id": None, "expected": []}])

    assert "- c1: A\n  前回用意した質問: Q" in text


def test_prompt_lists_points_explained_last_time_as_covered_only() -> None:
    text = _prompt(
        explained=[
            {"point_id": "p1", "point": "再送の仕組み", "question": "Q1", "status": "explained", "aspect_id": "a1"},
            {
                "point_id": "p2",
                "point": "窓の大きさ",
                "question": "Q2",
                "status": "explained_with_hint",
                "aspect_id": None,
            },
        ]
    )

    assert "## 前回説明できた要点" in text
    assert "- 再送の仕組み（観点: a1）\n- 窓の大きさ\n" in text
    assert "aspect_gap にしない" in text
    assert "source は covered" in text


def test_prompt_marks_no_explained_points() -> None:
    text = _prompt()

    assert "## 前回説明できた要点" in text
    assert text.count("（なし）") >= 4
