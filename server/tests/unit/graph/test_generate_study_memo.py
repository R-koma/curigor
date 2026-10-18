import asyncio
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from graph.output_schemas import ExploreMemoAspect, ExploreMemoOrganization, ExploreTermDraft
from graph.state import DepthMapState, LearningState

MAP: DepthMapState = {
    "topic": "二分探索",
    "aspects": [
        {
            "id": "前提",
            "name": "並んでいる前提",
            "is_core": False,
            "defined_question": "d",
            "reasoned_question": "r",
            "applied_question": "a",
        },
        {
            "id": "比較",
            "name": "真ん中との比較",
            "is_core": True,
            "defined_question": "d",
            "reasoned_question": "r",
            "applied_question": "a",
        },
    ],
}


def _state(**overrides: Any) -> LearningState:
    base: dict[str, Any] = {
        "user_id": "user-1",
        "dialogue_session_id": "00000000-0000-0000-0000-000000000001",
        "messages": [
            HumanMessage("二分探索って何？"),
            AIMessage("並んだ中から半分ずつ探す方法です", id="ai-answer"),
        ],
        "topic": "二分探索",
        "turn_count": 1,
        "should_generate_note": True,
        "session_type": "explore",
        "explore_terms": [{"term": "計算量", "reading": "", "meaning": "手間"}],
        "explore_questions": [
            {"question": "二分探索とは", "answer_message_id": "ai-answer"},
            {"question": "取り消した質問", "answer_message_id": "ai-removed"},
        ],
    }
    base.update(overrides)
    return cast(LearningState, base)


def _mock_pool() -> MagicMock:
    conn = AsyncMock()
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool


async def _run(
    state: LearningState,
    *,
    teachback: DepthMapState | None,
    fallback: DepthMapState | None,
    extracted: list[ExploreTermDraft] | None = None,
    organization: ExploreMemoOrganization | None = None,
) -> tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock]:
    insert = AsyncMock()
    teachback_mock = AsyncMock(return_value=teachback)
    fallback_mock = AsyncMock(return_value=fallback)
    organize_mock = AsyncMock(return_value=organization)
    with (
        patch("graph.nodes.generate_study_memo.get_pool", new=AsyncMock(return_value=_mock_pool())),
        patch("graph.nodes.generate_study_memo.study_memo_repository.insert", new=insert),
        patch("graph.nodes.generate_study_memo.summarize_answers", new=AsyncMock(return_value={0: "半分ずつ探す"})),
        patch("graph.nodes.generate_study_memo.extract_terms", new=AsyncMock(return_value=extracted or [])),
        patch("graph.nodes.generate_study_memo.draft_teachback_map", new=teachback_mock),
        patch("graph.nodes.generate_study_memo.generate_depth_map", new=fallback_mock),
        patch("graph.nodes.generate_study_memo.organize_memo", new=organize_mock),
    ):
        from graph.nodes.generate_study_memo import generate_study_memo

        assert await generate_study_memo(state) == {}
    return insert, teachback_mock, fallback_mock, organize_mock


ORGANIZATION = ExploreMemoOrganization(
    summary=" 半分ずつ探す方法を教わった ",
    aspects=[
        ExploreMemoAspect(aspect_id="比較", question_indices=[0], term_indices=[0]),
        ExploreMemoAspect(aspect_id="前提"),
    ],
)


async def test_saves_the_teachback_map_and_an_overview_of_its_aspects() -> None:
    insert, teachback, fallback, organize = await _run(
        _state(), teachback=MAP, fallback=None, organization=ORGANIZATION
    )

    teachback.assert_awaited_once()
    assert teachback.call_args.args[1] == [("二分探索とは", "並んだ中から半分ずつ探す方法です")]
    fallback.assert_not_awaited()
    organize.assert_awaited_once()
    args = organize.call_args.args
    assert args[0] == "二分探索"
    assert [a["id"] for a in args[1]] == ["比較", "前提"]
    assert args[2] == [("二分探索とは", "並んだ中から半分ずつ探す方法です")]
    assert args[3] == [{"term": "計算量", "reading": "", "meaning": "手間"}]
    kwargs = insert.call_args.kwargs
    assert kwargs["depth_map"] == MAP
    assert kwargs["summary"] == "半分ずつ探す方法を教わった"
    assert kwargs["overview"] == [
        {
            "aspect_id": "比較",
            "name": "真ん中との比較",
            "is_core": True,
            "question_indices": [0],
            "term_indices": [0],
        },
        {
            "aspect_id": "前提",
            "name": "並んでいる前提",
            "is_core": False,
            "question_indices": [],
            "term_indices": [],
        },
    ]
    assert kwargs["questions"] == [{"question": "二分探索とは", "answer": "半分ずつ探す"}]
    assert kwargs["glossary"] == [{"term": "計算量", "reading": "", "meaning": "手間"}]


async def test_saves_the_memo_without_a_summary_or_assignments_when_organizing_fails() -> None:
    insert, _, _, organize = await _run(_state(), teachback=MAP, fallback=None, organization=None)

    organize.assert_awaited_once()
    kwargs = insert.call_args.kwargs
    assert kwargs["summary"] == ""
    assert [(o["question_indices"], o["term_indices"]) for o in kwargs["overview"]] == [
        ([], []),
        ([], []),
    ]
    assert kwargs["questions"] == [{"question": "二分探索とは", "answer": "半分ずつ探す"}]
    assert kwargs["glossary"] == [{"term": "計算量", "reading": "", "meaning": "手間"}]


async def test_organizes_the_fallback_map_too() -> None:
    _, _, _, organize = await _run(_state(), teachback=None, fallback=MAP, organization=ORGANIZATION)

    assert [a["id"] for a in organize.call_args.args[1]] == ["比較", "前提"]


async def test_skips_organizing_when_there_are_no_aspects() -> None:
    insert, _, _, organize = await _run(_state(), teachback=None, fallback=None, organization=ORGANIZATION)

    organize.assert_not_awaited()
    assert insert.call_args.kwargs["summary"] == ""


async def test_skips_organizing_when_there_are_neither_answered_questions_nor_terms() -> None:
    state = _state(explore_terms=[], explore_questions=[])

    insert, _, _, organize = await _run(state, teachback=MAP, fallback=None, organization=ORGANIZATION)

    organize.assert_not_awaited()
    assert insert.call_args.kwargs["summary"] == ""
    assert len(insert.call_args.kwargs["overview"]) == 2


async def test_falls_back_to_a_topic_map_when_the_teachback_map_fails() -> None:
    insert, _, fallback, _ = await _run(_state(), teachback=None, fallback=MAP)

    assert fallback.call_args.kwargs["prior_knowledge"] == "ほとんど知らない（初めて学ぶ）"
    assert insert.call_args.kwargs["depth_map"] == MAP


async def test_saves_an_empty_map_when_both_maps_fail() -> None:
    insert, _, _, _ = await _run(_state(), teachback=None, fallback=None)

    assert insert.call_args.kwargs["depth_map"] == {"topic": "二分探索", "aspects": []}
    assert insert.call_args.kwargs["overview"] == []


async def test_terms_from_the_last_reply_join_the_glossary_and_the_teachback_map() -> None:
    draft = ExploreTermDraft(term="添字", reading="", meaning="位置を表す番号")
    insert, teachback, _, _ = await _run(_state(), teachback=MAP, fallback=None, extracted=[draft])

    assert {"term": "添字", "reading": "", "meaning": "位置を表す番号"} in insert.call_args.kwargs["glossary"]
    assert "添字" in [t["term"] for t in teachback.call_args.args[2]]


async def test_summarizes_the_answers_while_the_teachback_map_is_made() -> None:
    summary_may_finish = asyncio.Event()

    async def summarize(pairs: object) -> dict[int, str]:
        await summary_may_finish.wait()
        return {0: "半分ずつ探す"}

    async def teachback(*args: object) -> DepthMapState:
        summary_may_finish.set()
        return MAP

    insert = AsyncMock()
    with (
        patch("graph.nodes.generate_study_memo.get_pool", new=AsyncMock(return_value=_mock_pool())),
        patch("graph.nodes.generate_study_memo.study_memo_repository.insert", new=insert),
        patch("graph.nodes.generate_study_memo.summarize_answers", new=summarize),
        patch("graph.nodes.generate_study_memo.extract_terms", new=AsyncMock(return_value=[])),
        patch("graph.nodes.generate_study_memo.draft_teachback_map", new=teachback),
        patch("graph.nodes.generate_study_memo.generate_depth_map", new=AsyncMock(return_value=None)),
        patch("graph.nodes.generate_study_memo.organize_memo", new=AsyncMock(return_value=None)),
    ):
        from graph.nodes.generate_study_memo import generate_study_memo

        await asyncio.wait_for(generate_study_memo(_state()), timeout=1)

    assert insert.call_args.kwargs["questions"] == [{"question": "二分探索とは", "answer": "半分ずつ探す"}]


async def test_memo_from_an_improvement_saves_its_origin() -> None:
    gap = {
        "note_id": "n1",
        "feedback_id": "f1",
        "improvement_index": 2,
        "improvement": "計算量の説明が足りない",
        "note_content": "本文",
        "aspect_id": "a1",
    }
    insert, _, _, _ = await _run(_state(explore_gap=gap), teachback=MAP, fallback=None)

    assert insert.call_args.kwargs["origin"] == {
        "note_id": "n1",
        "feedback_id": "f1",
        "improvement_index": 2,
        "improvement": "計算量の説明が足りない",
        "aspect_id": "a1",
    }


async def test_memo_without_a_gap_has_no_origin() -> None:
    insert, _, _, _ = await _run(_state(), teachback=MAP, fallback=None)

    assert insert.call_args.kwargs["origin"] is None
