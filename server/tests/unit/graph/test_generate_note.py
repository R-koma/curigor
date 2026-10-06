import asyncio
import json
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from langchain_core.messages import HumanMessage

from graph.output_schemas import AspectMap, CollectionSuggestion, NoteCategory, NoteContent
from graph.state import LearningState

SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
USER_ID = "user-abc"

FAKE_NOTE_CONTENT = NoteContent(topic="Pythonの基礎", content="本文", summary="要約")


def _make_structured_mock(category_result: object) -> MagicMock:
    """with_structured_output(NoteContent | NoteCategory) を振り分けるモックを返す"""

    def _route(schema: type) -> AsyncMock:
        if schema is NoteCategory:
            return AsyncMock(ainvoke=AsyncMock(return_value=category_result))
        return AsyncMock(ainvoke=AsyncMock(return_value=FAKE_NOTE_CONTENT))

    return MagicMock(side_effect=_route)


def _make_state(**overrides: object) -> LearningState:
    base: dict[str, object] = {
        "user_id": USER_ID,
        "dialogue_session_id": SESSION_ID,
        "messages": [HumanMessage(content="Pythonとは何ですか？")],
        "topic": "Pythonの基礎",
        "turn_count": 3,
        "should_generate_note": True,
        "session_type": "learning",
    }
    base.update(overrides)
    return cast(LearningState, base)


def _mock_pool() -> tuple[MagicMock, AsyncMock]:
    conn = AsyncMock()
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool, conn


class TestGenerateNoteAspectMap:
    async def test_does_not_generate_the_aspect_map(self) -> None:
        pool, _ = _mock_pool()

        with (
            patch("graph.nodes.generate_note.get_pool", AsyncMock(return_value=pool)),
            patch("graph.nodes.generate_note.llm_structured") as mock_llm,
            patch(
                "graph.nodes.generate_note.note_repository.find_categories_by_user_id",
                AsyncMock(return_value=[]),
            ),
            patch("graph.nodes.generate_note.note_repository.insert", AsyncMock()) as mock_insert,
            patch("graph.nodes.generate_note.schedule_note_embedding", MagicMock()),
        ):
            mock_llm.with_structured_output = _make_structured_mock(NoteCategory(category="プログラミング"))

            from graph.nodes.generate_note import generate_note

            await generate_note(_make_state())
            await asyncio.sleep(0)

        assert mock_insert.call_args.kwargs["aspect_map"] is None
        schemas = [call.args[0] for call in mock_llm.with_structured_output.call_args_list]
        assert AspectMap not in schemas


class TestGenerateNoteCategory:
    async def test_category_estimated_and_passed_to_insert(self) -> None:
        pool, _ = _mock_pool()

        with (
            patch("graph.nodes.generate_note.get_pool", AsyncMock(return_value=pool)),
            patch("graph.nodes.generate_note.llm_structured") as mock_llm,
            patch(
                "graph.nodes.generate_note.note_repository.find_categories_by_user_id",
                AsyncMock(return_value=["数学"]),
            ),
            patch("graph.nodes.generate_note.note_repository.insert", AsyncMock()) as mock_insert,
        ):
            mock_llm.with_structured_output = _make_structured_mock(NoteCategory(category="プログラミング"))

            from graph.nodes.generate_note import generate_note

            await generate_note(_make_state())

        _, kwargs = mock_insert.call_args
        assert kwargs["category"] == "プログラミング"

    async def test_insert_called_with_none_when_category_llm_fails(self) -> None:
        pool, _ = _mock_pool()

        def _route(schema: type) -> AsyncMock:
            if schema is NoteCategory:
                return AsyncMock(ainvoke=AsyncMock(side_effect=RuntimeError("boom")))
            return AsyncMock(ainvoke=AsyncMock(return_value=FAKE_NOTE_CONTENT))

        with (
            patch("graph.nodes.generate_note.get_pool", AsyncMock(return_value=pool)),
            patch("graph.nodes.generate_note.llm_structured") as mock_llm,
            patch(
                "graph.nodes.generate_note.note_repository.find_categories_by_user_id",
                AsyncMock(return_value=[]),
            ),
            patch("graph.nodes.generate_note.note_repository.insert", AsyncMock()) as mock_insert,
        ):
            mock_llm.with_structured_output = MagicMock(side_effect=_route)

            from graph.nodes.generate_note import generate_note

            await generate_note(_make_state())

        _, kwargs = mock_insert.call_args
        assert kwargs["category"] is None

    async def test_insert_called_with_none_when_category_blank(self) -> None:
        pool, _ = _mock_pool()

        with (
            patch("graph.nodes.generate_note.get_pool", AsyncMock(return_value=pool)),
            patch("graph.nodes.generate_note.llm_structured") as mock_llm,
            patch(
                "graph.nodes.generate_note.note_repository.find_categories_by_user_id",
                AsyncMock(return_value=[]),
            ),
            patch("graph.nodes.generate_note.note_repository.insert", AsyncMock()) as mock_insert,
        ):
            mock_llm.with_structured_output = _make_structured_mock(NoteCategory(category="   "))

            from graph.nodes.generate_note import generate_note

            await generate_note(_make_state())

        _, kwargs = mock_insert.call_args
        assert kwargs["category"] is None


async def _insert_kwargs_for(state: LearningState) -> dict[str, object]:
    pool, _ = _mock_pool()
    with (
        patch("graph.nodes.generate_note.get_pool", AsyncMock(return_value=pool)),
        patch("graph.nodes.generate_note.llm_structured") as mock_llm,
        patch(
            "graph.nodes.generate_note.note_repository.find_categories_by_user_id",
            AsyncMock(return_value=[]),
        ),
        patch("graph.nodes.generate_note.note_repository.insert", AsyncMock()) as mock_insert,
    ):
        mock_llm.with_structured_output = _make_structured_mock(NoteCategory(category="OS"))

        from graph.nodes.generate_note import generate_note

        await generate_note(state)

    _, kwargs = mock_insert.call_args
    return dict(kwargs)


class TestGenerateNoteIntake:
    async def test_learning_premise_is_saved_as_json(self) -> None:
        kwargs = await _insert_kwargs_for(
            _make_state(learning_goal="基礎を学ぶ", learning_source="入門書", prior_knowledge="初めて")
        )

        assert json.loads(cast(str, kwargs["intake"])) == {
            "purpose": "基礎を学ぶ",
            "source": "入門書",
            "prior_knowledge": "初めて",
        }

    async def test_unanswered_fields_stay_blank_in_the_saved_premise(self) -> None:
        kwargs = await _insert_kwargs_for(_make_state(learning_source="入門書", prior_knowledge="  "))

        assert json.loads(cast(str, kwargs["intake"])) == {"purpose": "", "source": "入門書", "prior_knowledge": ""}

    async def test_intake_is_none_for_a_session_without_intake_keys(self) -> None:
        kwargs = await _insert_kwargs_for(_make_state())

        assert kwargs["intake"] is None

    async def test_intake_is_none_when_every_answer_is_blank(self) -> None:
        kwargs = await _insert_kwargs_for(_make_state(learning_goal="", learning_source=" ", prior_knowledge=""))

        assert kwargs["intake"] is None


def _make_suggestion_mock(suggestion: object) -> MagicMock:
    def _route(schema: type) -> AsyncMock:
        if schema is CollectionSuggestion:
            if isinstance(suggestion, Exception):
                return AsyncMock(ainvoke=AsyncMock(side_effect=suggestion))
            return AsyncMock(ainvoke=AsyncMock(return_value=suggestion))
        if schema is NoteCategory:
            return AsyncMock(ainvoke=AsyncMock(return_value=NoteCategory(category="OS")))
        return AsyncMock(ainvoke=AsyncMock(return_value=FAKE_NOTE_CONTENT))

    return MagicMock(side_effect=_route)


async def _run_with_suggestion(
    suggestion: object, *, existing: list[str], state: LearningState
) -> tuple[AsyncMock, MagicMock]:
    pool, _ = _mock_pool()
    with (
        patch("graph.nodes.generate_note.get_pool", AsyncMock(return_value=pool)),
        patch("graph.nodes.generate_note.llm_structured") as mock_llm,
        patch("graph.nodes.generate_note.note_repository.find_categories_by_user_id", AsyncMock(return_value=[])),
        patch(
            "graph.nodes.generate_note.note_collection_repository.find_names_by_user_id",
            AsyncMock(return_value=existing),
        ),
        patch("graph.nodes.generate_note.note_repository.insert", AsyncMock()) as mock_insert,
    ):
        mock_llm.with_structured_output = _make_suggestion_mock(suggestion)

        from graph.nodes.generate_note import generate_note

        await generate_note(state)
    return mock_insert, mock_llm.with_structured_output


class TestGenerateNoteCollectionSuggestion:
    async def test_suggestion_is_stored_on_the_note(self) -> None:
        mock_insert, _ = await _run_with_suggestion(
            CollectionSuggestion(name=" Linuxのしくみ "),
            existing=[],
            state=_make_state(learning_source="『Linuxのしくみ』"),
        )

        assert mock_insert.call_args.kwargs["suggested_collection"] == "Linuxのしくみ"

    async def test_no_source_and_no_collections_skips_the_llm(self) -> None:
        mock_insert, structured = await _run_with_suggestion(
            CollectionSuggestion(name="X"), existing=[], state=_make_state()
        )

        assert mock_insert.call_args.kwargs["suggested_collection"] is None
        assert CollectionSuggestion not in [c.args[0] for c in structured.call_args_list]

    async def test_existing_collections_are_offered_without_a_source(self) -> None:
        mock_insert, _ = await _run_with_suggestion(
            CollectionSuggestion(name="Linuxのしくみ"), existing=["Linuxのしくみ"], state=_make_state()
        )

        assert mock_insert.call_args.kwargs["suggested_collection"] == "Linuxのしくみ"

    async def test_blank_suggestion_is_stored_as_none(self) -> None:
        mock_insert, _ = await _run_with_suggestion(
            CollectionSuggestion(name="  "), existing=["A"], state=_make_state(learning_source="書籍")
        )

        assert mock_insert.call_args.kwargs["suggested_collection"] is None

    async def test_llm_failure_does_not_stop_note_generation(self) -> None:
        mock_insert, _ = await _run_with_suggestion(
            RuntimeError("boom"), existing=["A"], state=_make_state(learning_source="書籍")
        )

        assert mock_insert.call_args.kwargs["suggested_collection"] is None


async def test_flattened_escaped_newlines_are_saved_as_real_newlines() -> None:
    pool, _ = _mock_pool()
    flattened = NoteContent(topic="SRE", content="リード\\n\\n## 学んだこと\\n- SLO は目標値", summary="要約")

    def _route(schema: type) -> AsyncMock:
        if schema is NoteCategory:
            return AsyncMock(ainvoke=AsyncMock(return_value=NoteCategory(category="SRE")))
        return AsyncMock(ainvoke=AsyncMock(return_value=flattened))

    with (
        patch("graph.nodes.generate_note.get_pool", AsyncMock(return_value=pool)),
        patch("graph.nodes.generate_note.llm_structured") as mock_llm,
        patch("graph.nodes.generate_note.note_repository.find_categories_by_user_id", AsyncMock(return_value=[])),
        patch("graph.nodes.generate_note.note_repository.insert", AsyncMock()) as mock_insert,
    ):
        mock_llm.with_structured_output = MagicMock(side_effect=_route)

        from graph.nodes.generate_note import generate_note

        await generate_note(_make_state())

    _, kwargs = mock_insert.call_args
    assert kwargs["content"] == "リード\n\n## 学んだこと\n- SLO は目標値"
