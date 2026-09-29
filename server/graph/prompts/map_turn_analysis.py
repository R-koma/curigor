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
以下の順に判定する。2 を飛ばして 4 に進まない。

1. `observations`: 直近のユーザー発言で言及・説明された観点と、その発言で到達した段階
   - mentioned=名前を挙げただけ / defined=定義を自分の言葉で述べた /
     reasoned=なぜ必要か・どう動くかを述べた（日常の具体例を1つ挙げただけでは reasoned にしない）/
     applied=学習ゴールに沿った具体的な活用場面まで述べた
   - `aspect_id` は「この学習の観点地図」に載っている id をそのまま使う。
     地図に無い話題なら、id の代わりに分かりやすい仮の名前（日本語可）を入れてよい
2. `has_misconception`: 直近のユーザー発言に、訂正を要する誤り・混同が含まれるか
   - 述べられている内容が正しいかを、段階とは別に必ず検査する
   - 説明が浅い・言葉足らずなだけで、述べられている範囲は正しいものは誤りではない
3. `error_summary`: `has_misconception` が true なら、何がどう違うのかを 1 文で。false なら空文字
4. `response_mode`: 次の AI 応答のモード
   - `has_misconception` が true → 必ず reinforce
   - false のときだけ、段階で次のどちらかを選ぶ
     - deepen: 直近の説明が単一観点で reasoned 段階に届いていない
     - expand: 直近の説明が十分。複数観点が一度に列挙され各観点に最低限の定義があれば、
       個々の観点が defined 止まりでも expand を優先する
   - 到達目標は reasoned（なぜ・仕組みまで述べた）
5. `selected_aspect_id`: 次の応答で焦点を当てる観点を1つ
   - reinforce のときは、誤りを含む観点を選ぶ
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
