"""LLM が生成したテキストの性質を判定する deterministic check レジストリ。

判定ロジック自体は pure function で再現可能だが、検査対象（output）は
temperature 0.7 の LLM 生成テキストなので出力そのものは非決定的。
1 回の判定は安定していても、複数回生成した際の pass 率を見る前提は
eval 側（regression モード）が担う。ここでは判定ロジックと、その同一性を
表す fingerprint だけを持つ。
"""

from __future__ import annotations

import hashlib
import inspect
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import FunctionType

_GENERIC_PROMPT_PHRASES: tuple[str, ...] = (
    "もっと詳しく",
    "もう少し詳しく",
    "さらに詳しく",
    "掘り下げてみませんか",
    "考えてみませんか",
)


@dataclass(frozen=True)
class CheckOutcome:
    holds: bool
    detail: str


def contains_generic_prompt_phrase(output: str) -> CheckOutcome:
    """対象を特定しない一般化した促し（「もっと詳しく」「掘り下げてみませんか」等）を含むか。"""
    matched = [p for p in _GENERIC_PROMPT_PHRASES if p in output]
    return CheckOutcome(holds=bool(matched), detail=f"matched_phrases={matched}")


_STOCK_PRAISE_PHRASES: tuple[str, ...] = (
    "完璧",
    "素晴らしい",
    "すばらしい",
    "正解です",
    "100点",
    "大丈夫ですよ",
    "焦らなくて大丈夫",
)


def contains_stock_praise(output: str) -> CheckOutcome:
    """中身に触れない過剰な称賛・定型の励まし（「完璧」「素晴らしい」「大丈夫ですよ」等）を含むか。"""
    matched = [p for p in _STOCK_PRAISE_PHRASES if p in output]
    return CheckOutcome(holds=bool(matched), detail=f"matched_phrases={matched}")


_OPENING_DELIMITERS = r"[、。！？!?\n]"
_OPENING_MIN_CHARS = 4
_OPENING_WINDOW = 3


def _opening(text: str) -> str:
    return re.split(_OPENING_DELIMITERS, text.strip(), maxsplit=1)[0].strip()


def repeats_previous_opening(output: str, conversation_history: Sequence[Mapping[str, str]]) -> CheckOutcome:
    """応答の書き出し（最初の読点・句点まで）が、直近の AI 応答のいずれかの書き出しと同じか。"""
    opening = _opening(output)
    if len(opening) < _OPENING_MIN_CHARS:
        return CheckOutcome(holds=False, detail=f"opening={opening!r} (too short to compare)")
    previous = [_opening(m["content"]) for m in conversation_history if m["role"] == "assistant"][-_OPENING_WINDOW:]
    return CheckOutcome(holds=opening in previous, detail=f"opening={opening!r} previous_openings={previous}")


_REGISTRY: dict[str, Callable[[str], CheckOutcome]] = {
    "contains_generic_prompt_phrase": contains_generic_prompt_phrase,
    "contains_stock_praise": contains_stock_praise,
}

_HISTORY_REGISTRY: dict[str, Callable[[str, Sequence[Mapping[str, str]]], CheckOutcome]] = {
    "repeats_previous_opening": repeats_previous_opening,
}

_FINGERPRINT_DATA_TYPES = (str, bytes, int, float, tuple, frozenset, list, set, dict)


def _resolve(name: str) -> Callable[..., CheckOutcome]:
    if name in _REGISTRY:
        return _REGISTRY[name]
    if name in _HISTORY_REGISTRY:
        return _HISTORY_REGISTRY[name]
    available = (*_REGISTRY, *_HISTORY_REGISTRY)
    raise ValueError(f"unknown deterministic check: {name!r} (available: {available})")


def _implementation_parts(fn: FunctionType, seen: set[str]) -> list[str]:
    if fn.__qualname__ in seen:
        return []
    seen.add(fn.__qualname__)

    module = sys.modules[fn.__module__]
    parts = [inspect.getsource(fn)]
    # co_names は関数本体が参照するグローバル名。同一モジュールの定数とヘルパー関数だけを
    # 拾うことで、builtin・型・他モジュールからの import は自然に外れる。
    for name in sorted(fn.__code__.co_names):
        referent = getattr(module, name, None)
        if isinstance(referent, _FINGERPRINT_DATA_TYPES):
            parts.append(f"{name}={referent!r}")
        elif inspect.isfunction(referent) and referent.__module__ == fn.__module__:
            parts.extend(_implementation_parts(referent, seen))
    return parts


def check_fingerprint(name: str) -> str:
    """check の実装（関数本体 + 参照する定数・ヘルパー）の内容ハッシュ。"""
    fn = _resolve(name)
    if not isinstance(fn, FunctionType):
        raise ValueError(f"cannot fingerprint check {name!r}: not a plain function ({type(fn).__name__})")
    return hashlib.sha256("\x00".join(_implementation_parts(fn, set())).encode()).hexdigest()[:12]


def run_check(name: str, output: str, conversation_history: Sequence[Mapping[str, str]] = ()) -> CheckOutcome:
    """check 名で登録済み関数を解決して実行する。未登録なら fail-fast で ValueError。"""
    fn = _resolve(name)
    if name in _HISTORY_REGISTRY:
        return fn(output, conversation_history)
    return fn(output)
