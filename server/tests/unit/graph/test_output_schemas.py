import pytest

from graph.output_schemas import NoteContent, ReviewAddendum, SynthesisDraftOutput

FLATTENED_NOTE = (
    "SREは信頼性を保ちながら運用するための手法。\\n\\n## 学んだこと\\n- SLIは指標、SLOは目標値。"
    "\\n\\n## 重要なポイント\\n- エラーバジェットはリリース判断の材料になる。"
)


class TestNoteContentNewlines:
    def test_flattened_escaped_newlines_are_restored(self) -> None:
        note = NoteContent(topic="SRE", content=FLATTENED_NOTE, summary="要約")

        assert "\\n" not in note.content
        assert "\n## 学んだこと\n" in note.content
        assert note.content.splitlines()[0] == "SREは信頼性を保ちながら運用するための手法。"

    def test_escaped_crlf_becomes_newline(self) -> None:
        note = NoteContent(topic="t", content="リード\\r\\n\\r\\n## 学んだこと", summary="s")

        assert note.content == "リード\n\n## 学んだこと"

    @pytest.mark.parametrize(
        "content",
        [
            "リード\n\n## 学んだこと\n- 項目",
            'リード\n\n## 学んだこと\n- `print("a\\nb")` は改行を出力する',
        ],
    )
    def test_content_with_real_newlines_is_unchanged(self, content: str) -> None:
        assert NoteContent(topic="t", content=content, summary="s").content == content

    def test_topic_and_summary_are_not_unescaped(self) -> None:
        note = NoteContent(topic="改行\\n", content="本文", summary="`\\n` の扱い")

        assert note.topic == "改行\\n"
        assert note.summary == "`\\n` の扱い"


def test_review_addendum_restores_flattened_newlines() -> None:
    assert ReviewAddendum(content="- 項目1\\n- 項目2").content == "- 項目1\n- 項目2"


def test_synthesis_draft_restores_flattened_newlines() -> None:
    assert SynthesisDraftOutput(content="段落1 [N1]\\n\\n段落2 [N2]").content == "段落1 [N1]\n\n段落2 [N2]"
