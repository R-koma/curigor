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


_FENCED_BLOCK = re.compile(r"^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$", re.MULTILINE | re.DOTALL)
_OPEN_FENCE_TO_END = re.compile(r"^[ \t]*(`{3,}|~{3,}).*\Z", re.MULTILINE | re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_MATH_SPAN = re.compile(r"\$\$.+?\$\$|(?<![\\$])\$[^$\n]+?(?<!\\)\$", re.DOTALL)

_CODE_KEYWORDS = (
    "def",
    "class",
    "function",
    "const",
    "let",
    "var",
    "return",
    "import",
    "from",
    "#include",
    "public",
    "private",
    "SELECT",
    "INSERT",
    "UPDATE",
)
_CODE_KEYWORD_LINE = re.compile(r"^[ \t]*(" + "|".join(_CODE_KEYWORDS) + r")\b[^\n]*[(){}=;:]", re.MULTILINE)
_INDENTED_CODE_LINE = re.compile(r"^ {2,}(?![-*+]\s|\d+\.\s)\S[^\n]*[;{}:)][ \t]*$")
_JAPANESE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")

_LATEX_COMMANDS = (
    "frac",
    "dfrac",
    "sqrt",
    "int",
    "sum",
    "prod",
    "lim",
    "alpha",
    "beta",
    "gamma",
    "delta",
    "theta",
    "lambda",
    "mu",
    "pi",
    "sigma",
    "omega",
    "infty",
    "partial",
    "cdot",
    "times",
    "leq",
    "geq",
    "neq",
    "pm",
)
_LATEX_COMMAND = re.compile(r"\\(" + "|".join(_LATEX_COMMANDS) + r")\b")
_SUPERSCRIPT = re.compile(r"[A-Za-z0-9)\]]\^(\{[^}\n]*\}|-?[A-Za-z0-9])")
_SUBSCRIPT = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]_(\{[^}\n]*\}|[A-Za-z0-9])(?![A-Za-z0-9_])")

_PRICE_START = re.compile(r"(?<![\\$])\$(?=\d)")
_CLOSING_DOLLAR = re.compile(r"(?<!\\)\$")
_PROSE_IN_SPAN = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff、。]")

_MERMAID_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})[ \t]*mermaid\b", re.MULTILINE)


def _outside_code(text: str) -> str:
    without_blocks = _OPEN_FENCE_TO_END.sub("", _FENCED_BLOCK.sub("\n", text))
    return _INLINE_CODE.sub(" ", without_blocks)


def contains_unfenced_code(output: str) -> CheckOutcome:
    """フェンスとインラインコードの外に、コードの行があるか。"""
    text = _outside_code(output)
    keyword_lines = [m.group(0).strip() for m in _CODE_KEYWORD_LINE.finditer(text) if not _JAPANESE.search(m.group(0))]
    run: list[str] = []
    indented: list[str] = []
    for line in text.split("\n"):
        if _INDENTED_CODE_LINE.match(line):
            run.append(line.strip())
            continue
        if len(run) >= 2:
            indented.extend(run)
        run = []
    if len(run) >= 2:
        indented.extend(run)
    matched = keyword_lines + indented
    return CheckOutcome(holds=bool(matched), detail=f"code_lines={matched}")


def contains_unformatted_math(output: str) -> CheckOutcome:
    """`$` で囲んだ数式とコードの外に、LaTeX のコマンドや ^ _ の上付き・下付きがあるか。"""
    text = _MATH_SPAN.sub(" ", _outside_code(output))
    matched = [m.group(0) for pattern in (_LATEX_COMMAND, _SUPERSCRIPT, _SUBSCRIPT) for m in pattern.finditer(text)]
    return CheckOutcome(holds=bool(matched), detail=f"raw_math={matched}")


def contains_unescaped_price(output: str) -> CheckOutcome:
    """エスケープしていない $ の直後に数字があり、数式として閉じていない（金額として書いている）か。"""
    text = _outside_code(output)
    matched: list[str] = []
    for start in _PRICE_START.finditer(text):
        line_end = text.find("\n", start.end())
        rest = text[start.end() : line_end if line_end != -1 else len(text)]
        closing = _CLOSING_DOLLAR.search(rest)
        if closing is None or _PROSE_IN_SPAN.search(rest[: closing.start()]):
            matched.append(text[start.start() : start.end() + 6])
    return CheckOutcome(holds=bool(matched), detail=f"prices={matched}")


def contains_diagram(output: str) -> CheckOutcome:
    """```mermaid の図を含むか。"""
    matched = [m.group(0).strip() for m in _MERMAID_FENCE.finditer(output)]
    return CheckOutcome(holds=bool(matched), detail=f"diagrams={matched}")


_REGISTRY: dict[str, Callable[[str], CheckOutcome]] = {
    "contains_generic_prompt_phrase": contains_generic_prompt_phrase,
    "contains_stock_praise": contains_stock_praise,
    "contains_unfenced_code": contains_unfenced_code,
    "contains_unformatted_math": contains_unformatted_math,
    "contains_unescaped_price": contains_unescaped_price,
    "contains_diagram": contains_diagram,
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
