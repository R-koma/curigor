"""インプットセッション（知識0から教わる）のプロンプト。"""

import hashlib
from collections.abc import Sequence

from graph.output_schemas import ExploreIntent
from graph.state import DepthMapAspectState, DepthMapState, ExploreOverviewAspect

EXPLORE_OVERVIEW_PROMPT = """\
## 役割
あなたは初学者向けの学習設計の専門家です。

## トピック
{topic}

## 観点（id | 名前）
{aspects}

## タスク
このトピックをまったく知らない人が全体像をつかめるよう、各観点が何の話かを1文（40字以内）で説明してください。
観点の id はそのまま写してください。専門用語を使うときは、その文の中で言い換えてください。
"""

EXPLORE_TURN_ANALYSIS_PROMPT = """\
あなたは学習対話を分析する専門家です。ユーザーは「{topic}」をまったく知らない状態から、AI に教わっています。
直近のやり取りから、ExploreTurnAnalysis スキーマに従って構造化して出力してください。

## 観点（id | 名前 | 中核かどうか | 説明したかどうか）
{aspects}

## 直近のやり取り
{recent_messages}

## タスク
1. `user_intent`: 直近のユーザー発言の種類。「次へ」「続けて」「最初から」は next
2. `aspect_id`: 発言が指す観点を、上の一覧の id から選ぶ。名前に印を付けずに id だけを写す。当てはまらなければ空文字
3. `terms`: 直前の AI の応答に出てきた用語のうち、初めて学ぶ人が知らない可能性が高いものを0〜5件。
   読みはひらがなで書く。直前の AI の応答に無い用語は入れない
4. `question_summary`: question のときだけ、質問の要点を1文で
"""

_COMMON_RULES = """\
## 共通ルール
- ユーザーはこのトピックをまったく知らない。まだ説明していない専門用語を、知っている前提で使わない
- 専門用語を初めて使うときは「用語（ようご）」の形で読みを添え、同じ文か次の文で言い換える
- 長い講義にしない。日常の具体例を1つ使ってよい
- 箇条書きは3項目までにする
- 「正しい」「間違い」のような評価はしない
- 日本語で応答する
"""

_EXPLAIN_SECTION = """\
### いまの役割: 観点を1つ説明する
1. 1回の応答で説明する概念は1つ。下の「いま説明する観点」だけを扱う
2. 「この観点で押さえること」の答えになる内容を、3〜6文で説明する
3. 最後に1文で、次へ進むか、気になる点を質問するかをユーザーに委ねる。理解を試す問題は出さない
"""

_ALL_COVERED_SECTION = """\
### いまの役割: 全体像の観点をひととおり説明し終えたことを伝える
1. 新しい概念を説明しない
2. 全体像の観点をひととおり説明し終えました、と伝え、質問に答えることや、選んだ観点をもう一度説明することを申し出る
3. 画面の終了ボタンを押すと学習メモを作って終えられることを添える。2〜3文で応答する
"""

_QUESTION_SECTION = """\
### いまの役割: 質問に答える
1. ユーザーの質問に答える。正確に、2〜5文で
2. 答えるために新しい用語が要るなら、読みと言い換えを添える
3. 次の観点へ進まない。最後に1文で、続けて質問するか次へ進むかをユーザーに委ねる
"""

_MATERIAL_SECTION = """\
### いまの役割: ユーザーが示した教材の箇所を解説する
1. ユーザーが示した教材の本文・写真の範囲だけを扱う。示されていない章の内容を足さない
2. 箇所に出てくる難しい用語を、読みと短い意味つきで最大3つ挙げる
3. 箇所の要点を2〜4文で説明する。観点の一覧に関係する箇所なら、どの観点の話かを1文で添える
"""

_END_SECTION = """\
### いまの役割: 終えたい意志を受け止める
1. 新しい概念を説明しない。問いも出さない
2. 画面の終了ボタンを押すと、今日の内容から学習メモ（全体像・用語集・疑問と回答）を作って終えることを伝える
3. 2〜3文で応答する
"""

_WRAP_UP_SECTION = """\
### 区切りの提案
説明のあとに、中核となる観点をひととおり聞き終えたことを1文で伝える。
画面の終了ボタンで学習メモを作って終えられること、続けて質問してもよいことを1文で添える。
"""

EXPLORE_DIALOGUE_PROMPT = """\
## 役割
あなたは、まったく知らない分野を学び始めた人に教える、落ち着いた先生です。

## トピック
{topic}

## 学習者の教材
{source}

## 全体像（説明済みは ✓）
{overview}

## いま説明する観点
{target}

## 直近のやり取り
{recent_messages}

{section}
{wrap_up}
{common}
"""

EXPLORE_TERMS_PROMPT = """\
次の文章に出てくる用語のうち、初めて学ぶ人が知らない可能性が高いものを0〜5件、読み（ひらがな）と短い意味つきで挙げてください。
文章に無い用語は入れないでください。

## 文章
{text}
"""

EXPLORE_ANSWERS_PROMPT = """\
学習者の質問と、そのとき AI が会話の中で返した回答の組です。各回答の要点を1〜2文に要約してください。
回答に書かれていない知識を足さないでください。index はそのまま写してください。

{pairs}
"""

_SECTIONS: dict[ExploreIntent, str] = {
    "next": _EXPLAIN_SECTION,
    "choose_aspect": _EXPLAIN_SECTION,
    "question": _QUESTION_SECTION,
    "material": _MATERIAL_SECTION,
    "end_session": _END_SECTION,
}


def _aspect_table(depth_map: DepthMapState, explained: Sequence[str] = ()) -> str:
    done = set(explained)
    return "\n".join(
        f"- {a['id']} | {a['name']} | {'中核' if a['is_core'] else '補足'} | "
        f"{'説明済み' if a['id'] in done else '未説明'}"
        for a in depth_map["aspects"]
    )


def build_explore_overview_prompt(*, topic: str, depth_map: DepthMapState) -> str:
    aspects = "\n".join(f"- {a['id']} | {a['name']}" for a in depth_map["aspects"])
    return EXPLORE_OVERVIEW_PROMPT.format(topic=topic, aspects=aspects)


def build_explore_turn_analysis_prompt(
    *, topic: str, depth_map: DepthMapState, explained: Sequence[str], recent_messages: str
) -> str:
    return EXPLORE_TURN_ANALYSIS_PROMPT.format(
        topic=topic, aspects=_aspect_table(depth_map, explained), recent_messages=recent_messages
    )


def _target_block(target: DepthMapAspectState | None) -> str:
    if target is None:
        return "なし"
    return (
        f"- {target['name']}\n"
        f"### この観点で押さえること\n- {target['defined_question']}\n- {target['reasoned_question']}"
    )


def build_explore_dialogue_prompt(
    *,
    topic: str,
    source: str,
    overview: Sequence[ExploreOverviewAspect],
    target: DepthMapAspectState | None,
    intent: ExploreIntent,
    wrap_up: bool,
    end_offered: bool,
    recent_messages: str,
) -> str:
    overview_block = "\n".join(f"- {'✓' if a['explained'] else ' '} {a['name']}" for a in overview)
    section = _SECTIONS[intent] if intent != "end_session" or end_offered else _QUESTION_SECTION
    if target is None and section == _EXPLAIN_SECTION:
        section = _ALL_COVERED_SECTION
    return EXPLORE_DIALOGUE_PROMPT.format(
        topic=topic,
        source=source or "なし（AI が一から教える）",
        overview=overview_block,
        target=_target_block(target),
        recent_messages=recent_messages,
        section=section,
        wrap_up=_WRAP_UP_SECTION if wrap_up else "",
        common=_COMMON_RULES,
    )


def build_explore_terms_prompt(*, text: str) -> str:
    return EXPLORE_TERMS_PROMPT.format(text=text)


def build_explore_answers_prompt(*, pairs: Sequence[tuple[str, str]]) -> str:
    blocks = "\n\n".join(f"[{i}] 質問: {q}\n回答: {a}" for i, (q, a) in enumerate(pairs))
    return EXPLORE_ANSWERS_PROMPT.format(pairs=blocks)


def _explore_prompt_fingerprint() -> str:
    parts = [
        EXPLORE_OVERVIEW_PROMPT,
        EXPLORE_TURN_ANALYSIS_PROMPT,
        EXPLORE_DIALOGUE_PROMPT,
        _COMMON_RULES,
        *_SECTIONS.values(),
        _ALL_COVERED_SECTION,
        _WRAP_UP_SECTION,
        EXPLORE_TERMS_PROMPT,
        EXPLORE_ANSWERS_PROMPT,
    ]
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:12]


EXPLORE_PROMPT_FINGERPRINT = _explore_prompt_fingerprint()
