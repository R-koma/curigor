from collections.abc import Mapping, Sequence
from typing import Any

from graph.explore import ordered_aspects
from graph.state import DepthMapState, MemoTerm

MAX_MEMO_TERMS = 30


def memo_terms_from_glossary(glossary: Sequence[Mapping[str, Any]]) -> list[MemoTerm]:
    terms: list[MemoTerm] = []
    for entry in glossary:
        term = str(entry.get("term") or "").strip()
        if not term:
            continue
        terms.append({"term": term, "reading": str(entry.get("reading") or "").strip()})
    return terms[:MAX_MEMO_TERMS]


def memo_kickoff(topic: str, depth_map: DepthMapState) -> str:
    aspects = ordered_aspects(depth_map)
    start = f"まず「{aspects[0]['name']}」から、" if aspects else ""
    return (
        f"「{topic}」について教わった内容を、今度は自分の言葉で説明してみましょう。"
        f"{start}覚えている範囲で大丈夫です。断片的でも構いません。"
    )
