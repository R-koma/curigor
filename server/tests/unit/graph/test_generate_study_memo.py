from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from graph.output_schemas import ExploreTermDraft
from graph.state import DepthMapState, LearningState

MAP: DepthMapState = {
    "topic": "二分探索",
    "aspects": [
        {
            "id": "比較",
            "name": "真ん中との比較",
            "is_core": True,
            "defined_question": "d",
            "reasoned_question": "r",
            "applied_question": "a",
        }
    ],
}


def _state(**overrides: Any) -> LearningState:
    base: dict[str, Any] = {
        "user_id": "user-1",
        "dialogue_session_id": "00000000-0000-0000-0000-000000000001",
        "messages": [
            HumanMessage("二分探索"),
            AIMessage("全体像"),
            HumanMessage("なぜ並べるの？"),
            AIMessage("半分を捨てる判断に必要だからです", id="ai-answer"),
        ],
        "topic": "二分探索",
        "turn_count": 3,
        "should_generate_note": True,
        "session_type": "explore",
        "depth_map": MAP,
        "explore_overview": {"比較": "真ん中と比べる"},
        "explained_aspects": ["比較"],
        "explore_terms": [{"term": "計算量", "reading": "けいさんりょう", "meaning": "手間"}],
        "explore_questions": [
            {"question": "なぜ並べるのか", "answer_message_id": "ai-answer"},
            {"question": "取り消した質問", "answer_message_id": "ai-removed"},
        ],
        "learning_source": "入門書",
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


async def _run(state: LearningState, summaries: dict[int, str]) -> tuple[dict[str, Any], AsyncMock, AsyncMock]:
    insert = AsyncMock()
    summarize = AsyncMock(return_value=summaries)
    with (
        patch("graph.nodes.generate_study_memo.get_pool", new=AsyncMock(return_value=_mock_pool())),
        patch("graph.nodes.generate_study_memo.study_memo_repository.insert", new=insert),
        patch("graph.nodes.generate_study_memo.summarize_answers", new=summarize),
        patch(
            "graph.nodes.generate_study_memo.extract_terms",
            new=AsyncMock(return_value=[ExploreTermDraft(term="判断", reading="はんだん", meaning="決めること")]),
        ),
    ):
        from graph.nodes.generate_study_memo import generate_study_memo

        return await generate_study_memo(state), insert, summarize


async def test_saves_overview_glossary_and_answered_questions() -> None:
    result, insert, summarize = await _run(_state(), {0: "並んでいないと半分を捨てられない"})

    assert result == {}
    assert summarize.call_args.args[0] == [("なぜ並べるのか", "半分を捨てる判断に必要だからです")]
    kwargs = insert.call_args.kwargs
    assert kwargs["topic"] == "二分探索"
    assert kwargs["source"] == "入門書"
    assert kwargs["overview"] == [
        {
            "aspect_id": "比較",
            "name": "真ん中との比較",
            "summary": "真ん中と比べる",
            "is_core": True,
            "explained": True,
        }
    ]
    assert [t["term"] for t in kwargs["glossary"]] == ["計算量", "判断"]
    assert kwargs["questions"] == [{"question": "なぜ並べるのか", "answer": "並んでいないと半分を捨てられない"}]
    assert kwargs["depth_map"] == MAP


async def test_failed_summary_keeps_questions_without_answers() -> None:
    _, insert, _ = await _run(_state(), {})

    assert insert.call_args.kwargs["questions"] == [{"question": "なぜ並べるのか", "answer": ""}]


async def test_without_a_map_saves_nothing() -> None:
    result, insert, _ = await _run(_state(depth_map=None), {})

    assert result == {}
    insert.assert_not_called()
