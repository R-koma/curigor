"""ノートの「わからなかったこと」の節（「説明する」の途中に横の欄で質問して教わったこと）。"""

import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from graph.nodes._explore_llm import SideQuestionDigest

SIDE_SECTION_TITLE = "わからなかったこと"
SIDE_SECTION_HEADING = f"## {SIDE_SECTION_TITLE}"
_AMBIGUOUS_CALLOUT = "> **まだ曖昧な点**"


def _one_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def side_items(
    ordered: Sequence[Mapping[str, Any]], digests: Mapping[UUID, "SideQuestionDigest"]
) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for thread in ordered:
        digest = digests.get(thread["id"])
        if digest is None:
            continue
        if digest.term is not None and digest.term.meaning.strip():
            items.append((f"「{digest.term.term}」とは何か", digest.term.meaning))
        if digest.question and digest.answer:
            items.append((digest.question, digest.answer))
    return items


def build_side_section(items: Sequence[tuple[str, str]]) -> str:
    if not items:
        return ""
    lines = [SIDE_SECTION_HEADING]
    for question, answer in items:
        lines.append(f"- **{_one_line(question)}**")
        lines.append(f"  - {_one_line(answer)}")
    return "\n".join(lines)


def insert_side_section(content: str, section: str) -> str:
    if not section:
        return content
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line.startswith(_AMBIGUOUS_CALLOUT):
            before = "\n".join(lines[:i]).rstrip()
            after = "\n".join(lines[i:])
            return f"{before}\n\n{section}\n\n{after}"
    return f"{content.rstrip()}\n\n{section}"


def first_questions(threads: Sequence[Mapping[str, Any]]) -> list[str]:
    questions: list[str] = []
    for thread in threads:
        first = next((m["content"] for m in thread["messages"] if m["role"] == "user"), None)
        if first and first.strip():
            questions.append(first.strip())
    return questions
