"""地図駆動の学習対話の応答生成プロンプト。question.py のモード構造を再利用する。"""

import hashlib
from collections.abc import Sequence
from typing import Any, get_args

from graph.depth_map import format_map_coverage, next_stage, question_for
from graph.output_schemas import MapDialogueTurnAnalysis, MapUserIntent, ResponseMode
from graph.prompts import format_learning_plan_fields
from graph.prompts.map_turn_analysis import build_map_turn_analysis_prompt
from graph.prompts.question import (
    _MODE_EXAMPLES,
    MODE_DIALOGUE,
    MODE_HINT,
    MODE_UNKNOWN_A,
    MODE_UNKNOWN_B,
    MODE_UNKNOWN_C,
    MODE_WRAP_UP,
    QUESTION_PROMPT_BASE,
    UserIntent,
    build_mode_section,
    classify_user_intent,
)
from graph.state import DepthMapState, MapAspectProgress, MapStage, TopicCorrectionRecord, TopicCorrectionStatus

_OLD_GOAL = "ユーザーが各観点について「自分の言葉で説明でき、具体例または動作原理まで述べられる」状態を目標とする。"
_NEW_GOAL = (
    "ユーザーが各観点について「自分の言葉で説明でき、なぜ必要か・どう成り立つか（必要性・仕組み）まで述べられる」"
    "状態を目標とする。日常の具体例を1つ挙げられるだけでは到達とみなさない。"
)
_OLD_WRAP_UP_PHRASE = "具体例・動作原理以上まで説明できた観点"
_OLD_POLICY = (
    "- 断定的な正誤評価（「100点」「完璧」「正解です」「間違いです」）は行わない\n"
    "- 対話を促すポジティブな受け止め（「良い整理ですね」「重要なポイントを押さえていますね」）は許容する\n"
    "- ユーザーの説明に明確な誤りがある場合は、優しく訂正する"
)
_NEW_POLICY = (
    "- 「100点」「完璧」「正解です」のような過剰な称賛や、正解の断定はしない\n"
    "- 誤りのない説明への受け止めは、ユーザーの説明の中身に触れて1文で短く行う。決まった褒め言葉を使い回さない\n"
    "- ユーザーの説明に明確な誤りがある場合は、応答の最初に、どの部分が誤りかを明示する"
    "（例: 「〜という部分は誤りです」）。誤った説明を肯定する前置き（「整理していますね」「良い説明ですね」など）を"
    "付けない。説明の努力や人格は否定しない"
)

_OLD_LANGUAGE_RULE = "- 日本語で応答する\n"
_NEW_LANGUAGE_RULE = (
    "- 応答の書き出しは、直前までの AI 応答と変える。同じ句や同じ形の文で始めない\n"
    "- 問いは、一度読めば何を答えればよいかが分かる自然な日本語の1文にする。"
    "選ばせるときは、選ぶ候補を問いの中に示す。比べさせるときは「AとBでは何が違うか」のように比べる2つを並べて書き、"
    "「〜と比べて、〜では何が変わるか」のような回りくどい言い方をしない\n"
    "- 直前のやり取りと別の観点を問うときは、ユーザーの直前の発言の中身に触れ、"
    "それが新しい問いとどうつながるかを1文で示す。つながりが無いときは、「先ほどの〇〇の話に戻ると」のように、"
    "話を戻す・移すことを明示する。「では」「さて」だけで移らない\n"
    "- 日本語で応答する\n"
)

assert _OLD_GOAL in QUESTION_PROMPT_BASE
assert _OLD_WRAP_UP_PHRASE in MODE_WRAP_UP
assert _OLD_POLICY in QUESTION_PROMPT_BASE
assert QUESTION_PROMPT_BASE.count(_OLD_LANGUAGE_RULE) == 1

MAP_QUESTION_PROMPT_BASE = (
    QUESTION_PROMPT_BASE.replace(_OLD_GOAL, _NEW_GOAL)
    .replace(_OLD_POLICY, _NEW_POLICY)
    .replace(_OLD_LANGUAGE_RULE, _NEW_LANGUAGE_RULE)
)
_MAP_WRAP_UP = MODE_WRAP_UP.replace(_OLD_WRAP_UP_PHRASE, "なぜ・仕組みまで説明できた観点")

_UNMENTIONED_CONCEPT_RULE = (
    "ユーザーがまだ会話で口にしていない専門用語・概念を、知っている前提で問いや受け止めに入れない。"
    "その概念が必要なら、ユーザーが役割を自分で導ける問い（「〜が無いと何が困るか」）にするか、"
    "その用語が何を指すかだけを1文で示してから問う。用語の働きや理由（次の問いの答え）は示さない"
)

_MAP_DEEPEN_SECTION = """\
### モード C: 深掘り / 具体化（選んだ観点の必要性・仕組みを問う時）
選んだ観点について、なぜ必要か・どう成り立っているかを1つだけ問う。
- 「なぜ〜が必要か」「〜が無いと何が困るか」「どう成り立っているか」のいずれかを、下の核心の問いに沿って問う
- 日常の具体例を挙げさせない（目標段階が応用のときを除く）
- 既に述べた内容を、同じ深さで再説明させない
- 質問前に、その質問の答えとなる必要性や仕組みを解説しない

応答長の目安: 1〜3 文。
"""

_MAP_DEEPEN_EXAMPLE = """\
## モード C の応答例（形式を参考にし、例の話題を持ち込まない）
ユーザー: 「キューは先に入れたものを先に取り出す仕組みです」
AI: 「先に入れたものから取り出す、という順番が守られないと、何が困るのでしょうか？」
※ 具体例を挙げさせるのではなく、必要性・仕組みを問う。答えは先に示さない。
"""

_MAP_CORE_RULES = (
    "- 上の核心は、AI が向かう方向を示す内部の指針。応答の中で読み上げたり言い換えて述べたりしない\n"
    "- 核心に含まれる前提・対比・理由（「〜する一方」「〜できるため」など）は、"
    "ユーザーがまだ述べていなければ応答で先に述べない。それをユーザー自身が説明する問いにする。"
    "この規則は共通ルールの「前提の簡潔な補足はよい」より優先する。"
    "誤りそのものの訂正は述べてよい（控えるのは核心の理由づけ）\n"
    "- 観点名は内部のラベル。応答にそのまま出さず、ユーザーが使った言葉で言い換える"
)

_MAP_REINFORCE_STEP1 = (
    "1. 応答の最初に、ユーザーの説明のどの部分が誤りかを明示する（例: 「〜という部分は誤りです」）。\n"
    "   誤った説明を肯定・称賛する前置きを付けない。説明の努力や人格は否定しない"
)
_MAP_REINFORCE_STEP3 = (
    "3. 訂正した知識を使う問いを1つ出す。訂正文の一般則にそのまま当てはめるだけで答えが出る問い\n"
    "   （「〜を渡すと何になりますか」など）は避け、訂正した違いがどんな結果の差になるかや、\n"
    "   学習ゴールに沿った判断・対比を求める。「答えと理由」のように複数の要求を足さない\n"
    "   問いは応答全体で1つにする。疑問文のあとに「理由も〜」「〜も添えてください」のような別の文で要求を足さない。\n"
    "   選択の理由を聞きたい場合は、選ばせる問いと分けずに「〜を選ぶのはなぜか」の1つの問いにする\n"
    "   この手順は、共通ルールの「新しい例への適用で理解を確かめる」「必要な答えを具体的に示してよい」より優先する"
)

_MAP_REINFORCE_SECTION = f"""\
### モード A: 誤りの訂正（明確な誤り・重大な混同がある場合のみ）
手順:
{_MAP_REINFORCE_STEP1}
2. 正しい内容を短く示す。訂正は文で示し、コード例・例文を添えない。訂正は誤りの直接の修正にとどめ、次に考えてほしいこと
   （なぜ役立つか・どう使い分けるか）の答えまでは述べない。誤りのない説明済みの内容を解説し直さない
{_MAP_REINFORCE_STEP3}
4. 送信前に、今の問いの具体的な答えを訂正文・補足・例文で既に示していないか確認する。
   示していれば、未提示の結論を求める問いに直す

応答長の目安: 誤りの指摘と訂正 2〜4 行 + 質問 1 文。
"""

_MAP_REINFORCE_EXAMPLE = """\
## モード A の応答例（形式を参考にし、例の話題を持ち込まない）
ユーザー: 「中央値は全部の値を足して個数で割った値です」
悪い応答: 「説明しようとしていますね。足して個数で割るのは平均値で、中央値は並べた中央の値です。
では、2・9・4の中央値はいくつですか？」
→ 誤った説明を肯定する前置きで始まり、誤りだと伝わりにくい。問いも、今教えた定義を当てはめるだけで答えが出る。
良い応答: 「『足して個数で割る』という部分は誤りで、それは平均値の求め方です。
中央値は値を小さい順に並べたときの真ん中の値です。
では、極端に大きい値が1つだけ混ざったデータでは、平均値と中央値のどちらが全体の傾向を表しやすいでしょうか？」
→ 誤りの箇所を最初に明示し、訂正は定義の修正にとどめる。問いは、訂正した知識で平均値との違いを判断させる。
"""

_OLD_DIALOGUE_STEP1 = "1. 説明しようとした取り組みを短く受け止める。誤った内容を正しいと褒めない"
_OLD_DIALOGUE_STEP3 = (
    "3. 新しい事例または条件を示し、訂正した知識を使う適用・分類・判断を1つ求める。\n"
    "   定義や訂正文の言い換えを求めない。「答えと理由」のように複数の要求を足さない"
)

_OLD_DIALOGUE_EXAMPLE = _MODE_EXAMPLES["reinforce"].strip()

assert _OLD_DIALOGUE_STEP1 in MODE_DIALOGUE
assert _OLD_DIALOGUE_STEP3 in MODE_DIALOGUE
assert _OLD_DIALOGUE_EXAMPLE in MODE_DIALOGUE

_MAP_MODE_DIALOGUE = (
    MODE_DIALOGUE.replace(_OLD_DIALOGUE_STEP1, _MAP_REINFORCE_STEP1)
    .replace(_OLD_DIALOGUE_STEP3, _MAP_REINFORCE_STEP3)
    .replace(_OLD_DIALOGUE_EXAMPLE, _MAP_REINFORCE_EXAMPLE.strip())
)

_MODE_SECTIONS: dict[UserIntent, str] = {
    "exhausted": MODE_HINT,
    "unknown_a": MODE_UNKNOWN_A,
    "unknown_b": MODE_UNKNOWN_B,
    "unknown_c": MODE_UNKNOWN_C,
}


_MAP_DONT_KNOW_SECTION = f"""\
### モード: 「わからない」への支援
ユーザーは直前の問いに答えられなかった。
1. 受け止めは短くする。「大丈夫ですよ」のような定型の励ましで始めず、直前の AI 応答と違う書き出しにする
2. 直前の問いを言い換えて問い直さない。ユーザーがこれまでに述べた内容とつながる、一段手前の小さな問いを1つ出す
3. 問いに必要な前提が足りなければ、1〜2 文で補ってよい。ただし、出す問いの答えそのものは述べない
4. {_UNMENTIONED_CONCEPT_RULE}
5. 中断・終了・ノートの作成を提案しない
6. 「思いつくものでよいです」「無理に正解を出さなくて構いません」のような定型の結びを付けない

応答長の目安: 2〜4 文。
"""

_MAP_DONT_KNOW_REPEATED = """\
「わからない」が {streak} 回続いている。抽象的な問いをやめ、具体的な場面を1つ示して、その場面で何が起きるかを問う。
または、2〜3 個の選択肢から選んでもらう問いにする。
"""

_MAP_DONT_KNOW_PERSISTENT = """\
「わからない」が {streak} 回続いている。問いの形を変えて問い続けるのをやめ、答えを示す。
この指示は、上の手順 2・3（一段手前の問い・答えを述べない）より優先する。
1. 直前の問いの答えの中核を、2〜3 文で具体的に述べる
2. 述べた内容をそのまま問い返さない。述べていない新しい場面を1つ示し、述べた内容をそこに当てはめる問いを1つ出す
3. 区切りたいときは画面の「ノートを作成」で終えられることを、問いの前に1文で伝えてよい。末尾に選択肢として付けない

応答長の目安: 3〜5 文。

応答例（形式を参考にし、例の話題や書き出しを持ち込まない）
ユーザー: 「やっぱりわからないです」（3 回目）
AI: 「キューでは、先に並んだものから順に取り出します。後から来たものが先に処理されることはありません。
では、印刷待ちの書類が3枚あるところへ急ぎの1枚を足すと、その1枚は何番目に印刷されるでしょうか？」
"""

_MAP_PARTIAL_DONT_KNOW_SECTION = """\
### モード: 一部だけ「わからない」への支援
ユーザーは一部を説明し、別の一部がわからないと伝えた。
1. 説明できた部分は短く受け止める。言い直したり補強したりしない
2. わからない部分だけを扱う。ユーザーがすでに答えた内容を、別の言い方で再度求めない
3. わからない部分を考えるための足場（考えるための枠組み・具体的な場面）を 1〜2 文で渡し、
   それを使って答える問いを1つ出す。
   足場の中で、その問いの答えを述べない
4. 「大丈夫ですよ」のような定型の励ましや、「思いつくものでよいです」のような定型の結びを使わない

応答長の目安: 3〜5 文。
"""

_MAP_QUESTION_SECTION = """\
### モード: ユーザーの質問・依頼に答える
ユーザーは AI に質問したか、説明・具体例を頼んだ。
1. 最初に、質問・依頼に正確かつ簡潔に答える（1〜3 文）。具体例を頼まれたら、具体例を1つ示す
2. 答えの中で、下の核心の理由づけ（なぜ必要か・どう成り立つか）までは述べない。
   核心そのものを問われたら、考える方向だけを示す
3. 答えたあと、ユーザーがまだ解決していない疑問か、直前の話題につながる問いを1つ出す。
   別の観点へ移るときは、つながりを1文で示す。
   ユーザーの質問をそのまま聞き返したり、今答えた内容を言い換えて問うたりしない。
   答えた内容を、まだ述べていない場面に当てはめる問いにする
4. 示した答えや具体例の中に、次の問いの答えを書かない。
   場面の中で起きる結果（「〜しにくくなる」「〜が混ざらない」など）を述べたなら、その結果を問わない。
   問うのは、まだ述べていない理由・結果・別の場面にする

応答長の目安: 3〜6 文。
"""

_MAP_END_SESSION_SECTION = """\
### モード: セッションを終えたい
ユーザーはセッションを終えたい、またはノートを作ってほしいと伝えた。
1. 新しい問いを出さない。この手順は、共通ルールの問いの規則より優先する
2. 直前に説明した内容があれば、1 文で短く受け止める
3. 画面の「ノートを作成」を押すと、今日の内容からノートが作られると伝える
4. チャットの中で学習内容を要約したり、ノートを書いたりしない

応答長の目安: 2〜3 文。
"""


def _dont_know_section(streak: int) -> str:
    if streak >= 3:
        return _MAP_DONT_KNOW_SECTION + "\n" + _MAP_DONT_KNOW_PERSISTENT.format(streak=streak)
    if streak == 2:
        return _MAP_DONT_KNOW_SECTION + "\n" + _MAP_DONT_KNOW_REPEATED.format(streak=streak)
    return _MAP_DONT_KNOW_SECTION


_TOPIC_ACCEPTED_SECTION = """\
### モード: トピックの訂正を受け止める
ユーザーが学習トピックを「{previous_topic}」から「{new_topic}」へ訂正し、切り替えた。
1. 応答の最初に、トピックを「{new_topic}」に切り替えたことを1文で伝える。謝罪や言い訳を重ねない
2. 「{previous_topic}」についてのこれまでのやり取りを要約したり、続きを問うたりしない
3. 「{new_topic}」について、下の核心に向かう問いを1つ出す。答えや解説を先に述べない

応答長の目安: 2〜3 文。
"""

_TOPIC_DECLINED_SECTION = """\
### モード: トピックの変更を見送った
ユーザーは「{new_topic}」へのトピック変更を見送った。学習トピックは変えない。
1. 応答の最初に、トピックは変えずに続けることを1文で伝える
2. 下の核心に向かう問いを1つ出す。答えや解説を先に述べない

応答長の目安: 2〜3 文。
"""

_TOPIC_FAILED_SECTION = """\
### モード: トピックの訂正を切り替えられなかった
ユーザーが学習トピックを「{new_topic}」へ変えるよう求めたが、切り替えられなかった。学習トピックは「{previous_topic}」のまま。
1. 切り替えられなかったことと、トピックが「{previous_topic}」のままであることを1〜2文で伝える
2. もう一度トピックを伝えてほしいと頼む。問いは出さない
"""

_TOPIC_CORRECTION_SECTIONS: dict[TopicCorrectionStatus, str] = {
    "accepted": _TOPIC_ACCEPTED_SECTION,
    "declined": _TOPIC_DECLINED_SECTION,
    "failed": _TOPIC_FAILED_SECTION,
}


def _reached_stage(aspect_id: str, map_covered: Sequence[MapAspectProgress]) -> MapStage | None:
    for c in map_covered:
        if c["aspect_id"] == aspect_id:
            return c["reached_stage"]
    return None


def _build_map_dialogue_section(
    analysis: MapDialogueTurnAnalysis, depth_map: DepthMapState, map_covered: Sequence[MapAspectProgress]
) -> str:
    is_reinforce = analysis.response_mode == "reinforce"
    reinforce_body = _MAP_REINFORCE_SECTION if is_reinforce else None
    reinforce_example = _MAP_REINFORCE_EXAMPLE if is_reinforce else None
    aspect = next((a for a in depth_map["aspects"] if a["id"] == analysis.selected_aspect_id), None)
    if aspect is None:
        return build_mode_section(
            response_mode=analysis.response_mode,
            selected_aspect_label=analysis.selected_aspect_id,
            error_summary=analysis.error_summary,
            mode_body=reinforce_body,
            mode_example=reinforce_example,
        )
    target_stage = next_stage(_reached_stage(aspect["id"], map_covered))
    hint = (
        "### この観点の核心（地図より）\n"
        f"{question_for(aspect, target_stage)}\n"
        "この核心に向かって問いを組み立てる。日常的な具体例だけで終わらせない。\n"
        f"{_MAP_CORE_RULES}\n"
        f"- {_UNMENTIONED_CONCEPT_RULE}"
    )
    is_deepen = analysis.response_mode == "deepen"
    return build_mode_section(
        response_mode=analysis.response_mode,
        selected_aspect_label=aspect["name"],
        error_summary=analysis.error_summary,
        extra_hint=hint,
        mode_body=_MAP_DEEPEN_SECTION if is_deepen else reinforce_body,
        mode_example=_MAP_DEEPEN_EXAMPLE if is_deepen else reinforce_example,
    )


def _build_topic_correction_section(
    correction: TopicCorrectionRecord,
    analysis: MapDialogueTurnAnalysis | None,
    depth_map: DepthMapState,
    map_covered: Sequence[MapAspectProgress],
) -> str:
    section = _TOPIC_CORRECTION_SECTIONS[correction["status"]].format(
        previous_topic=correction["previous_topic"], new_topic=correction["new_topic"]
    )
    if correction["status"] == "failed":
        return section
    return _with_core_hint(section, analysis.selected_aspect_id if analysis else "", depth_map, map_covered)


def _with_core_hint(
    section: str, aspect_id: str, depth_map: DepthMapState, map_covered: Sequence[MapAspectProgress]
) -> str:
    aspect = next((a for a in depth_map["aspects"] if a["id"] == aspect_id), None)
    if aspect is None:
        return section
    target_stage = next_stage(_reached_stage(aspect["id"], map_covered))
    return f"{section}\n### この観点の核心（地図より）\n{question_for(aspect, target_stage)}\n{_MAP_CORE_RULES}\n"


def _build_intent_section(
    analysis: MapDialogueTurnAnalysis,
    unknown_streak: int,
    depth_map: DepthMapState,
    map_covered: Sequence[MapAspectProgress],
    wrap_up: bool,
) -> str:
    intent = analysis.user_intent
    aspect_id = analysis.selected_aspect_id
    if intent == "end_session":
        return _MAP_END_SESSION_SECTION
    if intent == "exhausted":
        return MODE_HINT
    if intent == "question":
        return _with_core_hint(_MAP_QUESTION_SECTION, aspect_id, depth_map, map_covered)
    if intent == "dont_know":
        return _with_core_hint(_dont_know_section(unknown_streak), aspect_id, depth_map, map_covered)
    if intent == "partial_dont_know" and not analysis.has_misconception:
        return _with_core_hint(_MAP_PARTIAL_DONT_KNOW_SECTION, aspect_id, depth_map, map_covered)
    if wrap_up:
        return _MAP_WRAP_UP
    return _build_map_dialogue_section(analysis, depth_map, map_covered)


def _build_coverage_section(map_covered: Sequence[MapAspectProgress], depth_map: DepthMapState) -> str:
    lines = format_map_coverage(map_covered, depth_map)
    if not lines:
        return ""
    return (
        "## カバー済み観点と到達度（過去ターン累積）\n"
        f"{lines}\n"
        "上記の観点は記載の段階まで説明済みとして扱い、同じ深さの質問を繰り返さない。\n\n"
    )


def build_map_question_prompt(
    *,
    topic: str,
    recent_messages: str,
    plan_fields: dict[str, str],
    messages: Sequence[Any],
    depth_map: DepthMapState,
    map_covered: Sequence[MapAspectProgress],
    turn_analysis: MapDialogueTurnAnalysis | None,
    wrap_up: bool = False,
    topic_correction: TopicCorrectionRecord | None = None,
    unknown_streak: int = 0,
) -> tuple[str, str]:
    """`turn_analysis` があればその `user_intent` で、無ければ（事前分析の失敗・旧 capture）キーワードで分岐する。"""
    keyword_intent = classify_user_intent(messages)
    intent: str = keyword_intent
    if topic_correction is not None and topic_correction["status"] in _TOPIC_CORRECTION_SECTIONS:
        mode_section = _build_topic_correction_section(topic_correction, turn_analysis, depth_map, map_covered)
    elif turn_analysis is not None:
        intent = turn_analysis.user_intent
        mode_section = _build_intent_section(turn_analysis, unknown_streak, depth_map, map_covered, wrap_up)
    elif keyword_intent == "dialogue" and wrap_up:
        mode_section = _MAP_WRAP_UP
    elif keyword_intent == "dialogue":
        mode_section = _MAP_MODE_DIALOGUE
    else:
        mode_section = _MODE_SECTIONS[keyword_intent]
    prompt = MAP_QUESTION_PROMPT_BASE.format(
        topic=topic,
        recent_messages=recent_messages,
        coverage_section=_build_coverage_section(map_covered, depth_map),
        **plan_fields,
    )
    return prompt + "\n" + mode_section, intent


def _map_prompt_fingerprint() -> str:
    """地図駆動の応答面（質問生成 + 地図の事前分析）の内容ハッシュ。"""
    dummy_map: DepthMapState = {
        "topic": "T",
        "aspects": [
            {
                "id": aspect_id,
                "name": aspect_id.upper(),
                "is_core": True,
                "defined_question": "D",
                "reasoned_question": "R",
                "applied_question": "P",
            }
            for aspect_id in ("a", "b", "c", "d", "e")
        ],
    }
    dummy_covered: list[MapAspectProgress] = [
        {"aspect_id": "a", "reached_stage": "mentioned"},
        {"aspect_id": "b", "reached_stage": "defined"},
        {"aspect_id": "c", "reached_stage": "reasoned"},
        {"aspect_id": "d", "reached_stage": "applied"},
    ]
    plan_fields = format_learning_plan_fields(learning_goal=None, focus_aspects=None)
    parts = [
        MAP_QUESTION_PROMPT_BASE,
        build_map_turn_analysis_prompt(
            topic="T", recent_messages="M", plan_fields=plan_fields, depth_map=dummy_map, map_covered=[]
        ),
        build_map_turn_analysis_prompt(
            topic="T", recent_messages="M", plan_fields=plan_fields, depth_map=dummy_map, map_covered=dummy_covered
        ),
        _MAP_MODE_DIALOGUE,
        *_MODE_SECTIONS.values(),
        _MAP_WRAP_UP,
        *(
            _build_intent_section(
                MapDialogueTurnAnalysis(
                    user_intent=intent,
                    observations=[],
                    has_misconception=False,
                    response_mode="deepen",
                    selected_aspect_id="a",
                ),
                streak,
                dummy_map,
                dummy_covered,
                False,
            )
            for intent in get_args(MapUserIntent)
            for streak in (1, 2, 3)
        ),
        _build_coverage_section(dummy_covered, dummy_map),
        *(
            _build_map_dialogue_section(
                MapDialogueTurnAnalysis(
                    observations=[],
                    has_misconception=True,
                    error_summary="E",
                    response_mode=mode,
                    selected_aspect_id=aspect_id,
                ),
                dummy_map,
                dummy_covered,
            )
            for mode in get_args(ResponseMode)
            for aspect_id in ("a", "b", "c", "d", "e", "missing")
        ),
        *(
            _build_topic_correction_section(
                {"previous_topic": "P", "new_topic": "N", "status": status},
                MapDialogueTurnAnalysis(
                    observations=[], has_misconception=False, response_mode="expand", selected_aspect_id="a"
                ),
                dummy_map,
                dummy_covered,
            )
            for status in _TOPIC_CORRECTION_SECTIONS
        ),
    ]
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:12]


MAP_PROMPT_FINGERPRINT = _map_prompt_fingerprint()
