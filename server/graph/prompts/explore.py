"""インプットセッション（疑問に答えて理解を深める）のプロンプト。"""

import hashlib
from collections.abc import Sequence

from graph.output_schemas import ExploreIntent
from graph.prompts._base import inject_formatting
from graph.state import DepthMapAspectState, ExploreGap, ExploreTerm

_TERM_SELECTION_RULES = """\
   - トピックを理解し説明するのに必要な概念だけを選ぶ。具体例や例え話の中で使っただけの言葉
     （例の分類名・業務や日常の一般的な言葉）は、トピックの概念でなければ入れない
   - 略語の正式名称・言い換え・訳語は別の用語にせず、略語の用語の意味に含める\
"""

EXPLORE_TURN_ANALYSIS_PROMPT = """\
あなたは学習対話を分析する専門家です。ユーザーはまったく知らない状態から、AI に疑問を聞きながら学んでいます。
直近のやり取りから、ExploreTurnAnalysis スキーマに従って構造化して出力してください。

## 今のトピック
{topic}

## 直近のやり取り
{recent_messages}

## タスク
1. `user_intent`: 直近のユーザー発言の種類
   - question: 質問・説明の依頼（「〇〇を知りたい」「〇〇って何？」も含む）
   - understood: 「わかった」「なるほど」のように納得を示し、新しい疑問を含まない
   - material: 教材の本文や写真を示して、その箇所の解説を求めた
   - end_session: 終えたい・学習メモを作ってほしい
   新しい疑問を含む「わかった」は question にする
2. `topic`: 直近のやり取りに AI の発言が無い最初のターンだけ、
   直近のユーザー発言と今のトピックから、学んでいる対象を短い名詞句（30字以内）で。
   目的・依頼の表現は含めない。
   AI の発言が既にあるときは空文字にする
3. `terms`: 直前の AI の応答に出てきた用語のうち、初めて学ぶ人が知らない可能性が高いものを0〜5件。
   意味は短く書く。読みは、会話の中で読み方が示された用語だけに書き、それ以外は空文字にする。
   直前の AI の応答に無い用語は入れない
{term_selection_rules}
4. `question_summary`: question と material のときだけ、疑問の要点を1文で
"""

_COMMON_RULES = """\
## 共通ルール
- ユーザーはこのトピックをまったく知らない。まだ説明していない専門用語を、知っている前提で使わない。
  使うときは同じ文か次の文で言い換える
- 用語に読み仮名を添えない。ユーザーが読み方を尋ねたときだけ答える
- 全体像を尋ねられたら、トピックを構成する主な要素を3〜5個、それぞれ1文で並べる
- 確かでないことや、あとで変わった可能性があること（バージョン・料金・最新の仕様・最近の出来事など）は、
  推測で言い切らない。確かな部分だけを答え、確かでない点はそう伝えて、公式の資料で確かめるよう促す
- 長い講義にしない。日常の具体例を1つ使ってよい。箇条書きは5項目までにする
- 「正しい」「間違い」のような評価はしない
- 日本語で応答する
"""

_QUESTION_SECTION = """\
### いまの役割: 疑問に答える
1. ユーザーの疑問に、正確に答える。2〜6文で
2. 直前までのユーザーの発言から、どこでつまずいているかを読み取り、そこに合わせて答える
3. 答えたら終える。理解を確かめる問いや、次に学ぶことの提案を添えない
"""

_MATERIAL_SECTION = """\
### いまの役割: ユーザーが示した教材の箇所を解説する
1. ユーザーが示した教材の本文・写真の範囲だけを扱う。示されていない章の内容を足さない
2. 箇所に出てくる難しい用語を、短い意味つきで最大3つ挙げる
3. 箇所の要点を2〜4文で説明する
"""

_UNDERSTOOD_SECTION = """\
### いまの役割: 納得を受け止める
1. 新しい概念を説明しない
2. 何がわかったかを、ユーザーの言葉に触れて1文で受け止める
3. ほかに気になっている点が無いかを短く尋ねる。1〜2文で
"""

_WRAP_UP_SECTION = """\
### いまの役割: 説明に移ることを提案する
1. 新しい概念を説明しない
2. 何がわかったかを、ユーザーの言葉に触れて1文で受け止める
3. ここまでの内容で学習メモを作り、自分の言葉で説明してみることを提案する。
   画面のボタンで学習メモを作って終えられること、続けて質問してもよいことを伝える。2〜3文で
"""

_END_SECTION = """\
### いまの役割: 終えたい意志を受け止める
1. 新しい概念を説明しない。問いも出さない
2. 画面の終了ボタンを押すと、今日の内容から学習メモ（疑問と回答・用語集・説明するときの観点）を作って終えることを伝える
3. 2〜3文で応答する
"""

_EXPLORE_DIALOGUE_TEMPLATE = """\
## 役割
あなたは、まったく知らない分野を学び始めた人の疑問に答える、落ち着いた先生です。
ユーザーの疑問を解消し、理解を深めることを目的にします。

## トピック
{topic}

## 直近のやり取り
{recent_messages}

{section}
{common}

{{FORMATTING}}
"""

EXPLORE_DIALOGUE_PROMPT = inject_formatting(_EXPLORE_DIALOGUE_TEMPLATE, diagrams=True, chat=True)
_EXPLORE_DIALOGUE_PROMPT_NO_DIAGRAM = inject_formatting(_EXPLORE_DIALOGUE_TEMPLATE, chat=True)

_GAP_ROLE = """\
## 役割
あなたは、学習者が説明できなかった部分を教える、落ち着いた先生です。
ユーザーは一度このトピックを自分の言葉で説明し、下の改善点の部分を説明できませんでした。
その部分はまだほとんど知らない前提で、教えて理解してもらうことを目的にします。
すでに説明できている部分（ノート本文）は教え直しません。ただし改善点に関わる部分は、ノートの書き方が正しいとは限らないので、
ノートを頼りにせず正しい内容を説明します。
"""

_GAP_CONTEXT = """\
## 改善点
{improvement}
{aspect_line}
## 本人が説明できた内容（ノート）
{note_content}

## 範囲
- 改善点の穴を埋めることを中心にする。ユーザーが別の疑問を聞いたら、その疑問に答える
"""

_GAP_ASPECT_LINE = "観点: {aspect_name}\n"

_GAP_OPENING_SECTION = """\
### いまの役割: 改善点の内容を教える
1. 改善点で説明できなかった内容を、まだほとんど知らない人に向けて、具体的に詳しく説明する。
   改善点を責める言い方で示さない。日常の具体例を1つ使ってよい
2. ノートに書いてある説明は繰り返さず、足りなかった部分を中心にする。改善点の範囲を超えて広げない
3. 最後に、気になるところや分からないところがあれば聞いてほしいと1文で添える。理解を確かめる問いは出さない
"""

_GAP_COMMON_RULES = """\
## 共通ルール
- ノート本文にあることは知っている前提でよい。ただし改善点に関わる部分は、
  ノートの書き方が正しいとは限らないので、ノートを頼りにせず正しい内容を説明する。
  改善点に関わる用語は、ノートにあっても知っている前提にせず、同じ文か次の文で言い換える
- 用語に読み仮名を添えない。ユーザーが読み方を尋ねたときだけ答える
- 全体像を尋ねられたら、トピックを構成する主な要素を3〜5個、それぞれ1文で並べる
- 確かでないことや、あとで変わった可能性があること（バージョン・料金・最新の仕様・最近の出来事など）は、
  推測で言い切らない。確かな部分だけを答え、確かでない点はそう伝えて、公式の資料で確かめるよう促す
- 改善点を教える最初の説明を除き、長い講義にしない。日常の具体例を1つ使ってよい。箇条書きは5項目までにする
- 「正しい」「間違い」のような評価はしない
- 日本語で応答する
"""

_EXPLORE_GAP_DIALOGUE_TEMPLATE = """\
{role}
## トピック
{topic}

{context}
## 直近のやり取り
{recent_messages}

{section}
{common}

{{FORMATTING}}
"""

_EXPLORE_GAP_DIALOGUE_PROMPT = inject_formatting(_EXPLORE_GAP_DIALOGUE_TEMPLATE, diagrams=True, chat=True)
_EXPLORE_GAP_DIALOGUE_PROMPT_NO_DIAGRAM = inject_formatting(_EXPLORE_GAP_DIALOGUE_TEMPLATE, chat=True)

EXPLORE_TERMS_PROMPT = """\
学習者は「{topic}」を学んでいます。
次の文章に出てくる用語のうち、初めて学ぶ人が知らない可能性が高いものを0〜5件、短い意味つきで挙げてください。
読み（ひらがな）は、文章の中で読み方が示されている用語だけに書き、それ以外は空文字にしてください。
文章に無い用語は入れないでください。
{term_selection_rules}

## 文章
{text}
"""

ANSWER_RECORD_RULE = "- 回答の要点に欠かせないコードや式は、言い換えて文章にせず、そのまま残す"

EXPLORE_ANSWERS_PROMPT = inject_formatting(
    """\
学習者の質問と、そのとき AI が会話の中で返した回答の組です。各回答の要点を1〜2文に要約してください。
回答に書かれていない知識を足さないでください。index はそのまま写してください。

{{FORMATTING}}
{answer_record_rule}

{pairs}
""",
).replace("{answer_record_rule}", ANSWER_RECORD_RULE)

EXPLORE_MEMO_ORGANIZE_PROMPT = inject_formatting(
    """\
学習者は「{topic}」について、AI に疑問を聞きながら教わりました。学習メモを整理するために、疑問と用語を観点に振り分け、
全体の要約を書いてください。

## 観点
{aspects}

## 疑問と回答
{pairs}

## 用語
{terms}

{{FORMATTING}}

## 厳守事項
- 観点の aspect_id は、上の `id` をそのまま写す
- question_indices は「疑問と回答」の [] の数字、term_indices は「用語」の [] の数字を、そのまま写す
- 一つの疑問・用語は、最も当たる観点一つにだけ入れる。どの観点にも当たらなければ、どこにも入れない
- 要約は、上の回答と用語の意味に書かれていることだけで書く。書かれていない知識を足さない
- 全体の要約は2〜4文にする
""",
)

EXPLORE_TEACHBACK_MAP_PROMPT = """\
## 役割
あなたは学習設計の専門家です。学習者は「{topic}」について、AI に疑問を聞きながら教わりました。
次は学習者が、教わった内容を自分の言葉で説明します。そのための観点を設計してください。

## 教わった疑問と回答
{pairs}

## 出てきた用語
{terms}

## タスク
DepthMapGeneration スキーマに従って、観点を2〜5個出力してください。各観点について:
1. `name`: 観点名（日本語の短い名詞句）
2. `is_core`: 教わった内容の中心にある観点なら true。中核は最大4個まで
3. `defined_question`: この観点を自分の言葉で定義できるかを問う核心
4. `reasoned_question`: なぜ必要か・どう成り立つかを問う核心。日常の具体例を挙げさせるだけの問いにしない
5. `applied_question`: 教わった内容を使う具体的な場面を問う核心

## 厳守事項
- 観点の数はスキーマの説明（3〜7個）ではなく、この指示の2〜5個と「会話で扱った内容だけ」を優先する
- 会話で扱っていない内容を観点にしない
- 核心の問いに、答えそのものを書かない
"""

_SECTIONS: dict[ExploreIntent, str] = {
    "question": _QUESTION_SECTION,
    "material": _MATERIAL_SECTION,
    "understood": _UNDERSTOOD_SECTION,
    "end_session": _END_SECTION,
}


def build_explore_turn_analysis_prompt(*, topic: str, recent_messages: str) -> str:
    return EXPLORE_TURN_ANALYSIS_PROMPT.format(
        topic=topic, recent_messages=recent_messages, term_selection_rules=_TERM_SELECTION_RULES
    )


def _section(intent: ExploreIntent, *, wrap_up: bool, end_offered: bool) -> str:
    if wrap_up:
        return _WRAP_UP_SECTION
    if intent == "end_session" and not end_offered:
        return _QUESTION_SECTION
    return _SECTIONS[intent]


def _gap_context(gap: ExploreGap) -> str:
    aspect_name = gap.get("aspect_name")
    return _GAP_CONTEXT.format(
        improvement=gap["improvement"],
        aspect_line=_GAP_ASPECT_LINE.format(aspect_name=aspect_name) if aspect_name else "",
        note_content=gap["note_content"],
    )


def build_explore_dialogue_prompt(
    *,
    topic: str,
    intent: ExploreIntent,
    wrap_up: bool,
    end_offered: bool,
    recent_messages: str,
    gap: ExploreGap | None = None,
    gap_opening: bool = False,
) -> str:
    if gap is not None and gap_opening:
        section = _GAP_OPENING_SECTION
    else:
        section = _section(intent, wrap_up=wrap_up, end_offered=end_offered)
    with_diagram = section in (_QUESTION_SECTION, _MATERIAL_SECTION, _GAP_OPENING_SECTION)
    if gap is None:
        template = EXPLORE_DIALOGUE_PROMPT if with_diagram else _EXPLORE_DIALOGUE_PROMPT_NO_DIAGRAM
        return template.format(
            topic=topic,
            recent_messages=recent_messages,
            section=section,
            common=_COMMON_RULES,
        )
    gap_template = _EXPLORE_GAP_DIALOGUE_PROMPT if with_diagram else _EXPLORE_GAP_DIALOGUE_PROMPT_NO_DIAGRAM
    return gap_template.format(
        role=_GAP_ROLE,
        topic=topic,
        context=_gap_context(gap),
        recent_messages=recent_messages,
        section=section,
        common=_GAP_COMMON_RULES,
    )


def build_explore_terms_prompt(*, topic: str, text: str) -> str:
    return EXPLORE_TERMS_PROMPT.format(topic=topic, text=text, term_selection_rules=_TERM_SELECTION_RULES)


def build_explore_answers_prompt(*, pairs: Sequence[tuple[str, str]]) -> str:
    blocks = "\n\n".join(f"[{i}] 質問: {q}\n回答: {a}" for i, (q, a) in enumerate(pairs))
    return EXPLORE_ANSWERS_PROMPT.format(pairs=blocks)


def build_explore_teachback_map_prompt(
    *, topic: str, pairs: Sequence[tuple[str, str]], terms: Sequence[ExploreTerm]
) -> str:
    pair_block = "\n".join(f"- 質問: {q}\n  回答: {a}" for q, a in pairs) or "なし"
    term_block = "\n".join(f"- {t['term']}: {t['meaning']}" for t in terms) or "なし"
    return EXPLORE_TEACHBACK_MAP_PROMPT.format(topic=topic, pairs=pair_block, terms=term_block)


def build_explore_memo_organize_prompt(
    *,
    topic: str,
    aspects: Sequence[DepthMapAspectState],
    pairs: Sequence[tuple[str, str]],
    terms: Sequence[ExploreTerm],
) -> str:
    aspect_block = "\n".join(f"- {a['id']}: {a['name']}" for a in aspects) or "なし"
    pair_block = "\n\n".join(f"[{i}] 質問: {q}\n回答: {a}" for i, (q, a) in enumerate(pairs)) or "なし"
    term_block = "\n".join(f"[{i}] {t['term']}: {t['meaning']}" for i, t in enumerate(terms)) or "なし"
    return EXPLORE_MEMO_ORGANIZE_PROMPT.format(topic=topic, aspects=aspect_block, pairs=pair_block, terms=term_block)


def _explore_prompt_fingerprint() -> str:
    parts = [
        EXPLORE_TURN_ANALYSIS_PROMPT,
        EXPLORE_DIALOGUE_PROMPT,
        _EXPLORE_DIALOGUE_PROMPT_NO_DIAGRAM,
        _COMMON_RULES,
        *_SECTIONS.values(),
        _WRAP_UP_SECTION,
        _EXPLORE_GAP_DIALOGUE_PROMPT,
        _EXPLORE_GAP_DIALOGUE_PROMPT_NO_DIAGRAM,
        _GAP_ROLE,
        _GAP_CONTEXT,
        _GAP_ASPECT_LINE,
        _GAP_OPENING_SECTION,
        _GAP_COMMON_RULES,
        EXPLORE_TERMS_PROMPT,
        _TERM_SELECTION_RULES,
        EXPLORE_ANSWERS_PROMPT,
        EXPLORE_TEACHBACK_MAP_PROMPT,
        EXPLORE_MEMO_ORGANIZE_PROMPT,
    ]
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:12]


EXPLORE_PROMPT_FINGERPRINT = _explore_prompt_fingerprint()
