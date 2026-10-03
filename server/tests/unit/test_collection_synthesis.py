from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from graph.output_schemas import SynthesisConnectionDraft, SynthesisContradictionDraft, SynthesisDraftOutput
from services.collection_synthesis import (
    NoteCountError,
    SourceNote,
    SynthesisGenerationError,
    build_connections,
    build_contradictions,
    build_notes_block,
    dialogue_connections,
    generate_synthesis,
    label_notes,
    note_content_hash,
    render_citations,
    snapshot,
    staleness,
)


def _note(content: str = "本文", revisions: tuple[str, ...] = ()) -> SourceNote:
    return SourceNote(id=uuid4(), topic="T", content=content, revisions=revisions)


class TestNoteContentHash:
    def test_changes_when_a_revision_is_appended(self) -> None:
        note = _note()
        revised = SourceNote(id=note.id, topic=note.topic, content=note.content, revisions=("- 追記",))

        assert note_content_hash(note) != note_content_hash(revised)

    def test_ignores_the_topic(self) -> None:
        note = _note()
        renamed = SourceNote(id=note.id, topic="別名", content=note.content, revisions=note.revisions)

        assert note_content_hash(note) == note_content_hash(renamed)


class TestStaleness:
    def test_fresh_when_nothing_changed(self) -> None:
        notes = [_note("a"), _note("b")]

        assert staleness(snapshot(notes), notes).is_stale is False

    def test_changed_content_is_reported(self) -> None:
        a, b = _note("a"), _note("b")
        recorded = snapshot([a, b])
        changed = SourceNote(id=b.id, topic=b.topic, content="b2", revisions=())

        result = staleness(recorded, [a, changed])

        assert result.is_stale is True
        assert result.changed_note_ids == [str(b.id)]

    def test_added_note_is_reported(self) -> None:
        a, b = _note("a"), _note("b")

        result = staleness(snapshot([a]), [a, b])

        assert result.is_stale is True
        assert result.changed_note_ids == [str(b.id)]

    def test_removed_note_makes_it_stale(self) -> None:
        a, b = _note("a"), _note("b")

        result = staleness(snapshot([a, b]), [a])

        assert result.is_stale is True
        assert result.changed_note_ids == []


def _labeled(*topics: str) -> dict[str, SourceNote]:
    return label_notes([SourceNote(id=uuid4(), topic=t, content=f"{t}の本文", revisions=()) for t in topics])


class TestRenderCitations:
    def test_replaces_known_labels_with_links(self) -> None:
        labeled = _labeled("プロセス", "システムコール")
        n1 = labeled["N1"]

        rendered = render_citations("プロセスは実行中のプログラム[N1]。", labeled)

        assert rendered == f"プロセスは実行中のプログラム[プロセス](/notes/{n1.id})。"

    def test_drops_unknown_labels(self) -> None:
        assert render_citations("説明[N9]。", _labeled("A")) == "説明。"

    def test_escapes_brackets_in_the_topic(self) -> None:
        labeled = _labeled("配列[]の扱い")

        assert "[配列［］の扱い](" in render_citations("x[N1]", labeled)


class TestBuildNotesBlock:
    def test_includes_revisions_under_each_note(self) -> None:
        labeled = label_notes([SourceNote(id=uuid4(), topic="A", content="本文", revisions=("- 追記",))])

        assert build_notes_block(labeled) == "### [N1] A\n本文\n\n#### 復習で深まった点\n- 追記"


class TestBuildConnections:
    def test_drops_connections_with_fewer_than_two_known_notes(self) -> None:
        labeled = _labeled("A", "B")
        drafts = [
            SynthesisConnectionDraft(note_labels=["N1", "N9"], title="片方だけ", explanation="e", question="q"),
            SynthesisConnectionDraft(note_labels=["[N1]", "N2"], title="両方", explanation="e", question="q"),
        ]

        connections = build_connections(drafts, labeled)

        assert [c["title"] for c in connections] == ["両方"]
        assert connections[0]["id"] == "c1"
        assert connections[0]["note_ids"] == [str(labeled["N1"].id), str(labeled["N2"].id)]

    def test_keeps_at_most_five(self) -> None:
        labeled = _labeled("A", "B")
        drafts = [
            SynthesisConnectionDraft(note_labels=["N1", "N2"], title=f"t{i}", explanation="e", question="q")
            for i in range(7)
        ]

        assert len(build_connections(drafts, labeled)) == 5

    def test_drops_contradictions_without_known_notes(self) -> None:
        labeled = _labeled("A")
        drafts = [
            SynthesisContradictionDraft(note_labels=["N5"], description="x"),
            SynthesisContradictionDraft(note_labels=["N1"], description="食い違い"),
        ]

        assert build_contradictions(drafts, labeled) == [
            {"note_ids": [str(labeled["N1"].id)], "description": "食い違い"}
        ]


def _pool() -> MagicMock:
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool


def _rows(count: int) -> list[dict[str, object]]:
    return [{"id": uuid4(), "topic": f"T{i}", "content": "c", "revisions": []} for i in range(count)]


async def _generate(rows: list[dict[str, object]], llm_result: object) -> AsyncMock:
    structured = MagicMock()
    if isinstance(llm_result, Exception):
        structured.ainvoke = AsyncMock(side_effect=llm_result)
    else:
        structured.ainvoke = AsyncMock(return_value=llm_result)
    with (
        patch("services.collection_synthesis.get_pool", AsyncMock(return_value=_pool())),
        patch(
            "services.collection_synthesis.note_collection_repository.find_by_id",
            AsyncMock(return_value={"id": uuid4(), "name": "Linuxのしくみ"}),
        ),
        patch(
            "services.collection_synthesis.note_repository.find_contents_by_collection_id",
            AsyncMock(return_value=rows),
        ),
        patch("services.collection_synthesis.llm_structured") as mock_llm,
        patch(
            "services.collection_synthesis.collection_synthesis_repository.upsert", AsyncMock(return_value={})
        ) as mock_upsert,
    ):
        mock_llm.with_structured_output = MagicMock(return_value=structured)
        await generate_synthesis(uuid4(), "user-1")
    return mock_upsert


class TestGenerateSynthesis:
    async def test_saves_the_rendered_draft_and_snapshot(self) -> None:
        rows = _rows(2)
        output = SynthesisDraftOutput(
            content="まとめ[N1][N2]",
            connections=[SynthesisConnectionDraft(note_labels=["N1", "N2"], title="t", explanation="e", question="q")],
            contradictions=[],
            gaps=[" 割り込み ", ""],
        )

        mock_upsert = await _generate(rows, output)

        kwargs = mock_upsert.call_args.kwargs
        assert kwargs["content"] == f"まとめ[T0](/notes/{rows[0]['id']})[T1](/notes/{rows[1]['id']})"
        assert kwargs["gaps"] == ["割り込み"]
        assert [s["note_id"] for s in kwargs["source_notes"]] == [str(r["id"]) for r in rows]

    async def test_rejects_a_single_note(self) -> None:
        with pytest.raises(NoteCountError):
            await _generate(_rows(1), None)

    async def test_rejects_more_than_thirty_notes(self) -> None:
        with pytest.raises(NoteCountError):
            await _generate(_rows(31), None)

    async def test_llm_failure_is_a_generation_error(self) -> None:
        with pytest.raises(SynthesisGenerationError):
            await _generate(_rows(2), RuntimeError("boom"))


class TestDialogueConnections:
    def test_keeps_the_top_three_without_note_ids(self) -> None:
        connections = [
            {"id": f"c{i}", "title": f"t{i}", "note_ids": ["a", "b"], "explanation": "e", "question": "q"}
            for i in range(1, 6)
        ]

        result = dialogue_connections(connections)

        assert [c["id"] for c in result] == ["c1", "c2", "c3"]
        assert "note_ids" not in result[0]
