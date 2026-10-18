import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import asyncpg
import pytest
import pytest_asyncio
from langchain_core.messages import BaseMessage

from graph.output_schemas import ReviewPlanGeneration, ReviewPlanPointDraft
from graph.prompts.review_plan import REVIEW_PLAN_PROMPT_FINGERPRINT
from repositories import dialogue_session_repository, feedback_repository, review_plan_repository
from services import review_plan
from services.review_plan import generate_review_plan, plan_note_hash

pytestmark = pytest.mark.asyncio(loop_scope="session")

CONTENT = "## 学んだこと\n- 再送で信頼性を保つ\n\n## まだ曖昧な点\n- タイムアウトの決め方"
ASPECT_MAP = {
    "root": "TCP",
    "aspects": [
        {"name": "再送制御", "summary": "送り直す", "coverage": "partial", "children": []},
        {"name": "輻輳制御", "summary": "量を絞る", "coverage": "covered", "children": []},
    ],
}


def _draft(point: str, **kwargs: Any) -> ReviewPlanPointDraft:
    fields: dict[str, Any] = {
        "point": point,
        "question": f"{point}を説明してください",
        "expected": ["項目1", "項目2"],
        "source": "aspect_gap",
        "aspect_id": "a1",
        "in_note": True,
    }
    return ReviewPlanPointDraft(**{**fields, **kwargs})


class _FakeRunnable:
    def __init__(self, owner: "_FakeLLM") -> None:
        self.owner = owner

    async def ainvoke(self, messages: list[BaseMessage], config: dict[str, Any] | None = None) -> Any:
        self.owner.prompts.append(str(messages[0].content))
        self.owner.configs.append(config or {})
        if self.owner.fail:
            raise RuntimeError("boom")
        return self.owner.result


class _FakeLLM:
    def __init__(self, drafts: list[ReviewPlanPointDraft] | None = None, *, fail: bool = False) -> None:
        self.result = ReviewPlanGeneration(points=drafts if drafts is not None else [_draft("再送の仕組み")])
        self.fail = fail
        self.prompts: list[str] = []
        self.configs: list[dict[str, Any]] = []
        self.tasks: list[str] = []

    def with_structured_output(self, schema: type, *, task: str) -> _FakeRunnable:
        assert schema is ReviewPlanGeneration
        self.tasks.append(task)
        return _FakeRunnable(self)


@pytest_asyncio.fixture(loop_scope="session", autouse=True)
async def _use_test_pool(test_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None]:
    async def fake_get_pool() -> asyncpg.Pool:
        return test_pool

    monkeypatch.setattr(review_plan, "get_pool", fake_get_pool)
    yield


def _use_llm(monkeypatch: pytest.MonkeyPatch, llm: _FakeLLM) -> _FakeLLM:
    monkeypatch.setattr(review_plan, "llm_structured", llm)
    return llm


async def _note(conn: asyncpg.Connection, user_id: str, review_count: int | None = None) -> uuid.UUID:
    note_id = uuid.uuid4()
    await conn.execute(
        """--sql
        INSERT INTO notes (id, user_id, topic, content, summary, status, aspect_map)
        VALUES ($1, $2, 'TCP', $3, '要約', 'active', $4::jsonb)
        """,
        note_id,
        user_id,
        CONTENT,
        json.dumps(ASPECT_MAP, ensure_ascii=False),
    )
    if review_count is not None:
        await conn.execute(
            """--sql
            INSERT INTO review_schedules (id, note_id, review_count, next_review_at, status)
            VALUES (gen_random_uuid(), $1, $2, now(), 'pending')
            """,
            note_id,
            review_count,
        )
    return note_id


async def _feedback(
    conn: asyncpg.Connection,
    note_id: uuid.UUID,
    user_id: str,
    *,
    improvement_items: list[dict[str, Any]] | None = None,
    review_results: list[dict[str, Any]] | None = None,
) -> None:
    session_id = uuid.uuid4()
    await dialogue_session_repository.create(
        conn=conn, session_id=session_id, user_id=user_id, session_type="review", graph_version=1, note_id=note_id
    )
    await feedback_repository.insert(
        conn,
        note_id=note_id,
        dialogue_session_id=session_id,
        understanding_level="medium",
        strength="s",
        improvements="i",
        improvement_items=json.dumps(improvement_items or [], ensure_ascii=False),
        review_results=json.dumps(review_results, ensure_ascii=False) if review_results is not None else None,
    )


def _result(point_id: str, point: str, status: str) -> dict[str, Any]:
    question = f"前回の{point}の質問"
    return {"point_id": point_id, "point": point, "question": question, "status": status, "aspect_id": "a1"}


async def test_generate_saves_points_and_hash(
    db_conn: asyncpg.Connection, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    llm = _use_llm(monkeypatch, _FakeLLM())
    note_id = await _note(db_conn, test_user["id"], review_count=2)
    await _feedback(
        db_conn, note_id, test_user["id"], improvement_items=[{"text": "タイムアウトが曖昧", "aspect_id": "a1"}]
    )

    points = await generate_review_plan(note_id, test_user["id"])

    row = await review_plan_repository.find_by_note_id(db_conn, note_id, test_user["id"])
    assert points is not None and row is not None
    assert row["points"] == points
    assert points[0]["id"] == "p1" and points[0]["point"] == "再送の仕組み"
    assert row["note_content_hash"] == plan_note_hash(CONTENT, [])
    assert row["prompt_fingerprint"] == REVIEW_PLAN_PROMPT_FINGERPRINT
    assert llm.tasks == ["generate-review-plan"]
    assert llm.configs[0]["run_name"] == "generate-review-plan"
    assert llm.configs[0]["metadata"] == {"prompt_fingerprint": REVIEW_PLAN_PROMPT_FINGERPRINT}
    prompt = llm.prompts[0]
    assert "タイムアウトが曖昧（観点: a1）" in prompt
    assert "a1: 再送制御（partial）" in prompt
    assert "完了した復習: 2 回" in prompt


async def test_generate_includes_revisions_in_the_prompt_and_hash(
    db_conn: asyncpg.Connection, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    llm = _use_llm(monkeypatch, _FakeLLM())
    note_id = await _note(db_conn, test_user["id"])
    session_id = uuid.uuid4()
    await dialogue_session_repository.create(
        conn=db_conn,
        session_id=session_id,
        user_id=test_user["id"],
        session_type="review",
        graph_version=1,
        note_id=note_id,
    )
    await db_conn.execute(
        """--sql
        INSERT INTO note_revisions (id, note_id, dialogue_session_id, content)
        VALUES (gen_random_uuid(), $1, $2, $3)
        """,
        note_id,
        session_id,
        "復習で足した説明",
    )

    await generate_review_plan(note_id, test_user["id"])

    row = await review_plan_repository.find_by_note_id(db_conn, note_id, test_user["id"])
    assert row is not None
    assert row["note_content_hash"] == plan_note_hash(CONTENT, ["復習で足した説明"])
    assert "復習で足した説明" in llm.prompts[0]
    assert "完了した復習: 0 回" in llm.prompts[0]


async def test_generate_carries_over_unexplained_results(
    db_conn: asyncpg.Connection, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    llm = _use_llm(
        monkeypatch,
        _FakeLLM([_draft("新しい要点"), _draft("言い換えた A", source="carryover", carryover_key="c1")]),
    )
    note_id = await _note(db_conn, test_user["id"], review_count=1)
    await _feedback(
        db_conn,
        note_id,
        test_user["id"],
        review_results=[
            _result("p1", "A", "not_explained"),
            _result("p2", "B", "explained"),
            _result("p3", "C", "not_asked"),
        ],
    )

    points = await generate_review_plan(note_id, test_user["id"])

    prompt = llm.prompts[0]
    assert "c1: A" in prompt and "c2: C" in prompt
    assert prompt.count("前回のAの質問") == 2
    assert prompt.count("前回のBの質問") == 1
    assert prompt.count("前回のCの質問") == 1
    assert points is not None
    carried = [p for p in points if p["source"] == "carryover"]
    assert [p["point"] for p in carried] == ["A", "C"]


async def test_regeneration_keeps_plan_carryover_whose_id_collides_with_a_result(
    db_conn: asyncpg.Connection, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    note_id = await _note(db_conn, test_user["id"], review_count=1)
    old_carry = {**_draft("Old").model_dump(), "id": "p9", "source": "carryover", "aspect_id": "a1"}
    await review_plan_repository.upsert(db_conn, note_id, json.dumps([old_carry], ensure_ascii=False), "h", "fp")
    await _feedback(
        db_conn,
        note_id,
        test_user["id"],
        review_results=[
            _result("p1", "X", "explained"),
            _result("p2", "Y", "explained"),
            _result("p3", "B", "not_explained"),
        ],
    )
    _use_llm(monkeypatch, _FakeLLM([_draft("Old を別の聞き方で", source="carryover", carryover_key="c2")]))
    first = await generate_review_plan(note_id, test_user["id"])
    assert first is not None
    assert [(p["id"], p["point"]) for p in first if p["source"] == "carryover"] == [("p1", "Old"), ("p2", "B")]

    llm = _use_llm(monkeypatch, _FakeLLM([_draft("別の要点")]))
    second = await generate_review_plan(note_id, test_user["id"])

    assert second is not None
    assert sorted(p["point"] for p in second if p["source"] == "carryover") == ["B", "Old"]
    assert "前回のXの質問" in llm.prompts[0]


async def test_plan_written_after_the_feedback_still_carries_its_unexplained_points(
    db_conn: asyncpg.Connection, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    note_id = await _note(db_conn, test_user["id"], review_count=1)
    await _feedback(db_conn, note_id, test_user["id"], review_results=[_result("p1", "A", "not_explained")])
    edited_plan = [{**_draft("Old").model_dump(), "id": "p1", "source": "carryover", "aspect_id": "a1"}]
    await review_plan_repository.upsert(db_conn, note_id, json.dumps(edited_plan, ensure_ascii=False), "h", "fp")
    _use_llm(monkeypatch, _FakeLLM([_draft("別の要点")]))

    points = await generate_review_plan(note_id, test_user["id"])

    assert points is not None
    assert [p["point"] for p in points if p["source"] == "carryover"] == ["A", "Old"]


async def test_generate_returns_none_and_keeps_old_plan_when_llm_fails(
    db_conn: asyncpg.Connection, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    note_id = await _note(db_conn, test_user["id"])
    old_point = {**_draft("Old").model_dump(), "id": "p1"}
    await review_plan_repository.upsert(db_conn, note_id, json.dumps([old_point]), "old-hash", "fp")
    _use_llm(monkeypatch, _FakeLLM(fail=True))

    assert await generate_review_plan(note_id, test_user["id"]) is None

    row = await review_plan_repository.find_by_note_id(db_conn, note_id, test_user["id"])
    assert row is not None
    assert row["points"] == [old_point] and row["note_content_hash"] == "old-hash"


async def test_generate_returns_none_without_points(
    db_conn: asyncpg.Connection, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    note_id = await _note(db_conn, test_user["id"])
    _use_llm(monkeypatch, _FakeLLM([_draft("期待なし", expected=[])]))

    assert await generate_review_plan(note_id, test_user["id"]) is None
    assert await review_plan_repository.find_by_note_id(db_conn, note_id, test_user["id"]) is None


async def test_generate_returns_none_for_other_users_note(
    db_conn: asyncpg.Connection, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    llm = _use_llm(monkeypatch, _FakeLLM())
    note_id = await _note(db_conn, test_user["id"])

    assert await generate_review_plan(note_id, "someone-else") is None
    assert llm.prompts == []
    assert await review_plan_repository.find_by_note_id(db_conn, note_id, test_user["id"]) is None


async def test_schedule_runs_in_the_background_and_swallows_errors(
    db_conn: asyncpg.Connection, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    note_id = await _note(db_conn, test_user["id"])

    async def boom(note_id: uuid.UUID, user_id: str) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(review_plan, "generate_review_plan", boom)
    review_plan.schedule_review_plan(note_id, test_user["id"])
    pending = list(review_plan._pending)

    assert len(pending) == 1
    await pending[0]
    assert pending[0].exception() is None


async def test_generate_passes_points_explained_last_time_to_the_prompt(
    db_conn: asyncpg.Connection, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    llm = _use_llm(monkeypatch, _FakeLLM())
    note_id = await _note(db_conn, test_user["id"], review_count=1)
    await _feedback(
        db_conn,
        note_id,
        test_user["id"],
        review_results=[
            _result("p1", "A", "explained"),
            _result("p2", "B", "explained_with_hint"),
            _result("p3", "C", "not_explained"),
            _result("p4", "D", "not_asked"),
        ],
    )

    await generate_review_plan(note_id, test_user["id"])

    section = llm.prompts[0].split("## 前回説明できた要点", 1)[1].split("\n## ", 1)[0]
    assert "- A（観点: a1）" in section
    assert "- B（観点: a1）" in section
    assert "C" not in section and "D" not in section
