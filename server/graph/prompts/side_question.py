"""インプットセッションで、応答の一部を選んで横で尋ねた疑問（横の質問）のプロンプト。"""

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from graph.prompts._base import inject_formatting
from graph.prompts.explore import EXPLORE_COMMON_RULES

_SIDE_QUESTION_TEMPLATE = """\
## 役割
あなたは、まったく知らない分野を学び始めた人の疑問に答える、落ち着いた先生です。
ユーザーは AI の説明を読みながら、その一部を選んで、本筋の会話とは別の欄で質問しています。
選んだ箇所についての疑問に答えることを目的にします。

## トピック
{topic}

## 選んだ箇所を含む文
{anchor_text}

## 選んだ箇所
「{quote}」

## 本筋の直近のやり取り
{recent_messages}

## この質問のもとになった横の質問
{ancestors}

## 同じセッションで横で尋ねたほかの質問
{other_side_questions}

### いまの役割: 選んだ箇所についての疑問に答える
1. 選んだ箇所についての疑問に、正確に、短く答える。2〜6文で
2. 選んだ箇所が語 1 つで、意味を尋ねられたら、辞書の一般的な意味ではなく、上の文の中での意味を答える
3. 本筋のやり取りと、ほかの横の質問で説明済みのことは、知っている前提で答えてよい
4. 答えたら終える。理解を確かめる問いや、次に学ぶことの提案を添えない

{common}

{{FORMATTING}}
"""

SIDE_QUESTION_PROMPT = inject_formatting(_SIDE_QUESTION_TEMPLATE, chat=True)

SIDE_QUESTION_PROMPT_FINGERPRINT = hashlib.sha256(
    "\x00".join([SIDE_QUESTION_PROMPT, EXPLORE_COMMON_RULES]).encode()
).hexdigest()[:12]

_NONE = "なし"
ANSWER_EXCERPT_CHARS = 200
QUESTION_EXCERPT_CHARS = 300


def build_side_question_prompt(
    *, topic: str, anchor_text: str, quote: str, recent_messages: str, ancestors: str, other_side_questions: str
) -> str:
    return SIDE_QUESTION_PROMPT.format(
        topic=topic,
        anchor_text=anchor_text,
        quote=quote,
        recent_messages=recent_messages or _NONE,
        ancestors=ancestors or _NONE,
        other_side_questions=other_side_questions or _NONE,
        common=EXPLORE_COMMON_RULES,
    )


def format_side_thread(thread: Mapping[str, Any]) -> str:
    lines = [f"選んだ箇所: 「{thread['quote']}」"]
    lines += [f"{'ユーザー' if m['role'] == 'user' else 'AI'}: {m['content']}" for m in thread["messages"]]
    return "\n".join(lines)


def _excerpt(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _thread_summary(thread: Mapping[str, Any]) -> str:
    questions = [m["content"] for m in thread["messages"] if m["role"] == "user"]
    answers = [m["content"] for m in thread["messages"] if m["role"] == "assistant"]
    lines = [
        f"- 選んだ箇所: 「{thread['quote']}」",
        f"  質問: {_excerpt(' / '.join(questions), QUESTION_EXCERPT_CHARS)}",
    ]
    if answers:
        lines.append(f"  答えの要点: {_excerpt(' '.join(answers), ANSWER_EXCERPT_CHARS)}")
    return "\n".join(lines)


def format_side_questions_for_context(threads: Sequence[Mapping[str, Any]], *, max_chars: int) -> str:
    picked: list[str] = []
    used = 0
    for thread in reversed(threads):
        block = _thread_summary(thread)
        if used + len(block) + 1 > max_chars:
            continue
        picked.append(block)
        used += len(block) + 1
    return "\n".join(reversed(picked))
