"""地図駆動の学習対話 1 ターンの事前分析プロンプト。graph/prompts/turn_analysis.py の地図版。"""

from graph.depth_map import format_map_coverage
from graph.prompts._base import inject_charter
from graph.state import DepthMapState, MapAspectProgress

MAP_TURN_ANALYSIS_PROMPT = inject_charter(
    """\
あなたは学習対話の 1 ターンを分析する専門家です。
ユーザーが「{topic}」について自分の言葉で説明しています。
直近のユーザー発言を分析し、MapDialogueTurnAnalysis スキーマに従って構造化して出力してください。

## 学習プラン
- 学習ゴール: {learning_goal}
- 重視する観点: {focus_aspects}

## この学習の観点地図
{aspect_list}

## これまでにカバー済みの観点と到達度（過去ターン累積）
{coverage_block}

## 対話履歴（直近のみ）
{recent_messages}

## タスク
以下の順に判定する。3 を飛ばして 5 に進まない。

0. `corrected_topic`: 直近のユーザー発言が、学習トピックそのものの変更・訂正を求めているか
   - 例: 「この仕組みって言ったけど間違えた。Linuxの仕組みに変更して」→ `Linuxの仕組み`
   - 観点の話題が移っただけ・関連する別の概念を説明しているだけ・質問しているだけは訂正ではない
   - 訂正なら新しいトピックの短い名詞句（30字以内）を入れ、`observations` は空にする。
     訂正でなければ空文字にして、以下を通常どおり判定する
1. `user_intent`: 直近のユーザー発言の種類
   - explanation: 学習内容を自分の言葉で説明している
   - dont_know: 説明できる内容がなく、わからないと伝えている
     （例: 「わかりません」「まだよくわかりません。それが何の役に立つのか思いつきません」）
   - partial_dont_know: 一部を説明しつつ、別の一部がわからないと伝えている
     （例: 「取り出す順番を守るためだと思います。ただ、それでなぜ速くなるのかはわかりません」）。
     「わからない」という語を含んでも、説明している部分があればこちら
   - question: AI への質問、または説明・具体例の依頼
     （例: 「スタックとキューは何が違うんですか？」「先に例を見せてもらえますか？」）
   - exhausted: 説明できることが尽きた（例: 「以上です」「他は思いつきません」）。セッションを終えたいわけではない
   - end_session: セッションを終えたい、またはノートを作ってほしいと伝えている
     （例: 「今日はこのへんで終わります」「ノートを作ってください」）。説明と一緒でもこちらを優先する
   - 説明している部分があれば、どの種類でも 2〜4 を通常どおり判定する。説明が無ければ observations は空、
     has_misconception は false にする
2. `observations`: 直近のユーザー発言で言及・説明された観点と、その発言で到達した段階
   - mentioned=名前を挙げただけ / defined=定義を自分の言葉で述べた /
     reasoned=なぜ必要か・どう動くかを述べた（日常の具体例を1つ挙げただけでは reasoned にしない）/
     applied=学習ゴールに沿った具体的な活用場面まで述べた
   - `aspect_id` は「この学習の観点地図」に載っている id をそのまま使う。
     地図に無い話題なら、id の代わりに分かりやすい仮の名前（日本語可）を入れてよい
3. `has_misconception`: 直近のユーザー発言に、訂正を要する誤り・混同が含まれるか
   - 述べられている内容が正しいかを、段階とは別に必ず検査する
   - 説明が浅い・言葉足らずなだけで、述べられている範囲は正しいものは誤りではない
4. `error_summary`: `has_misconception` が true なら、何がどう違うのかを 1 文で。false なら空文字
5. `response_mode`: 次の AI 応答のモード
   - `has_misconception` が true → 必ず reinforce
   - false のときだけ、段階で次のどちらかを選ぶ
     - deepen: 直近の説明が単一観点で reasoned 段階に届いていない
     - expand: 直近の説明が十分。複数観点が一度に列挙され各観点に最低限の定義があれば、
       個々の観点が defined 止まりでも expand を優先する
   - 到達目標は reasoned（なぜ・仕組みまで述べた）
   - 説明が無いとき（dont_know・question・exhausted・end_session で説明部分が無い）は deepen にする
6. `selected_aspect_id`: 次の応答で焦点を当てる観点を1つ
   - reinforce のときは、誤りを含む観点を選ぶ
   - dont_know・partial_dont_know のときは、直前の AI の問いが扱っていた観点を選ぶ
   - question のときは、質問が関わる観点を選ぶ
   - それ以外の選定基準: 中核観点の未到達 > 到達度が reasoned に最も届いていない既出観点 > 既出順
   - observations と同じ解決規則で id または仮の名前を使う

## 厳守事項
{{NO_FABRICATION}}
"""
)

_EMPTY_COVERAGE_PLACEHOLDER = "（まだなし）"


def _format_aspect_list(depth_map: DepthMapState) -> str:
    lines = []
    for a in depth_map["aspects"]:
        core_mark = "（中核）" if a["is_core"] else ""
        lines.append(f"- id: {a['id']} / {a['name']}{core_mark}")
    return "\n".join(lines)


def build_map_turn_analysis_prompt(
    *,
    topic: str,
    recent_messages: str,
    plan_fields: dict[str, str],
    depth_map: DepthMapState,
    map_covered: list[MapAspectProgress],
) -> str:
    coverage_block = format_map_coverage(map_covered, depth_map) or _EMPTY_COVERAGE_PLACEHOLDER
    return MAP_TURN_ANALYSIS_PROMPT.format(
        topic=topic,
        recent_messages=recent_messages,
        aspect_list=_format_aspect_list(depth_map),
        coverage_block=coverage_block,
        **plan_fields,
    )
