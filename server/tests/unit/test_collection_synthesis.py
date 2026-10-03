from uuid import uuid4

from services.collection_synthesis import SourceNote, note_content_hash, snapshot, staleness


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
