"""本筋とは別の欄で尋ねた疑問（横の質問）のプロンプト。"""

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from graph.prompts._base import inject_formatting
from graph.prompts.explore import EXPLORE_BRIEF_RULES

_EXPLORE_ROLE = """\
## 役割
あなたは、まったく知らない分野を学び始めた人の疑問に答える、落ち着いた先生です。
ユーザーは AI の説明を読みながら、その一部を選んで、本筋の会話とは別の欄で質問しています。
選んだ箇所についての疑問に答えることを目的にします。"""

_EXPLORE_ROLE_WITHOUT_QUOTE = """\
## 役割
あなたは、まったく知らない分野を学び始めた人の疑問に答える、落ち着いた先生です。
ユーザーは AI の説明を読みながら、本筋の会話とは別の欄で質問しています。
疑問に答えることを目的にします。"""

_LEARNING_ROLE = """\
## 役割
あなたは、学んだことを自分の言葉で説明する練習をしている人の疑問に答える、落ち着いた先生です。
ユーザーは本筋の会話で AI に説明をしている途中で、分からないことを本筋とは別の欄で質問しています。
質問に答えることを目的にします。"""

_TOPIC_SECTION = """\
## トピック
{topic}"""

_PASSAGE_SECTION = """\
## 選んだ箇所を含む文
{anchor_text}

## 選んだ箇所
「{quote}」"""

_CONTEXT_SECTION = """\
## 本筋の直近のやり取り
{recent_messages}

## この質問のもとになった横の質問
{ancestors}

## 同じセッションで横で尋ねたほかの質問
{other_side_questions}"""

_EXPLORE_RULES = """\
### いまの役割: 選んだ箇所についての疑問に答える
1. 選んだ箇所についての疑問に、正確に、短く答える。2〜6文で
2. 選んだ箇所が語 1 つで、意味を尋ねられたら、辞書の一般的な意味ではなく、上の文の中での意味を答える
3. 本筋のやり取りと、ほかの横の質問で説明済みのことは、知っている前提で答えてよい
4. 答えたら終える。理解を確かめる問いや、次に学ぶことの提案を添えない"""

_EXPLORE_RULES_WITHOUT_QUOTE = """\
### いまの役割: 疑問に答える
1. 疑問に、正確に、短く答える。2〜6文で
2. 本筋のやり取りと、ほかの横の質問で説明済みのことは、知っている前提で答えてよい
3. 答えたら終える。理解を確かめる問いや、次に学ぶことの提案を添えない"""

LEARNING_SIDE_RULES = """\
### いまの役割: 質問に答える
1. 質問に、正確に答える。詳しさは質問の大きさに合わせる
2. 選んだ箇所が語 1 つで、意味を尋ねられたら、辞書の一般的な意味ではなく、上の文の中での意味を答える
3. 本筋のやり取りと、ほかの横の質問で説明済みのことは、知っている前提で答えてよい
4. 答えたら終える。理解を確かめる問いや、次に学ぶことの提案を添えない。本筋の説明に戻るよう促さない"""

_LEARNING_SIDE_RULES_WITHOUT_QUOTE = """\
### いまの役割: 質問に答える
1. 質問に、正確に答える。詳しさは質問の大きさに合わせる
2. 本筋のやり取りと、ほかの横の質問で説明済みのことは、知っている前提で答えてよい
3. 答えたら終える。理解を確かめる問いや、次に学ぶことの提案を添えない。本筋の説明に戻るよう促さない"""

_LEARNING_COMMON_RULES = """\
## 共通ルール
- 確かでないことや、あとで変わった可能性があること（バージョン・料金・最新の仕様・最近の出来事など）は、
  推測で言い切らない。確かな部分だけを答え、確かでない点はそう伝えて、公式の資料で確かめるよう促す
- 長い講義にしない。箇条書きは5項目までにする
- ユーザーの本筋の説明を「正しい」「間違い」のように評価しない
- 日本語で応答する
"""

_FORMATTING_SECTION = "{{FORMATTING}}\n"


def _template(session_type: str, *, has_quote: bool) -> str:
    learning = session_type == "learning"
    if learning:
        role = _LEARNING_ROLE
        rules = LEARNING_SIDE_RULES if has_quote else _LEARNING_SIDE_RULES_WITHOUT_QUOTE
    else:
        role = _EXPLORE_ROLE if has_quote else _EXPLORE_ROLE_WITHOUT_QUOTE
        rules = _EXPLORE_RULES if has_quote else _EXPLORE_RULES_WITHOUT_QUOTE
    sections = [role, _TOPIC_SECTION, *([_PASSAGE_SECTION] if has_quote else []), _CONTEXT_SECTION, rules]
    return inject_formatting("\n\n".join([*sections, "{common}", _FORMATTING_SECTION]), chat=True)


_TEMPLATES = {
    (session_type, has_quote): _template(session_type, has_quote=has_quote)
    for session_type in ("explore", "learning")
    for has_quote in (True, False)
}


def _fingerprint_source() -> str:
    return "\x00".join([*_TEMPLATES.values(), EXPLORE_BRIEF_RULES, _LEARNING_COMMON_RULES])


SIDE_QUESTION_PROMPT_FINGERPRINT = hashlib.sha256(_fingerprint_source().encode()).hexdigest()[:12]

_NONE = "なし"
ANSWER_EXCERPT_CHARS = 200
QUESTION_EXCERPT_CHARS = 300


def build_side_question_prompt(
    *,
    session_type: str,
    topic: str,
    anchor_text: str,
    quote: str,
    recent_messages: str,
    ancestors: str,
    other_side_questions: str,
) -> str:
    learning = session_type == "learning"
    template = _TEMPLATES[("learning" if learning else "explore", bool(quote))]
    return template.format(
        topic=topic,
        anchor_text=anchor_text,
        quote=quote,
        recent_messages=recent_messages or _NONE,
        ancestors=ancestors or _NONE,
        other_side_questions=other_side_questions or _NONE,
        common=_LEARNING_COMMON_RULES if learning else EXPLORE_BRIEF_RULES,
    )


def format_side_thread(thread: Mapping[str, Any]) -> str:
    lines = [f"選んだ箇所: 「{thread['quote']}」"] if thread["quote"] else []
    lines += [f"{'ユーザー' if m['role'] == 'user' else 'AI'}: {m['content']}" for m in thread["messages"]]
    return "\n".join(lines)


def _excerpt(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _thread_summary(thread: Mapping[str, Any]) -> str:
    questions = [m["content"] for m in thread["messages"] if m["role"] == "user"]
    answers = [m["content"] for m in thread["messages"] if m["role"] == "assistant"]
    question = f"質問: {_excerpt(' / '.join(questions), QUESTION_EXCERPT_CHARS)}"
    lines = [f"- 選んだ箇所: 「{thread['quote']}」", f"  {question}"] if thread["quote"] else [f"- {question}"]
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
