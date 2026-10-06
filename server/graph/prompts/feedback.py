"""フィードバック生成プロンプト（generate_feedback / update_note_and_feedback ノード共有）。"""

from typing import Any

from graph.aspect_map import iter_aspects
from graph.prompts._base import inject_charter

GENERATE_FEEDBACK_PROMPT = inject_charter(
    """\
## 役割
あなたは学習評価の専門家です。
ユーザーの対話分析結果に厳密に基づいて評価し、{topic} に関する一般知識で補完しないこと。

## 目的
ユーザーの学習対話の分析結果とノートに基づき、理解度の評価とフィードバックを提供します。

## 対話の分析結果
{analysis}
{aspect_section}
## 評価基準
### understanding_level（理解度）
- high: コア概念を正確に説明でき、具体例や応用例にも言及できている。誤解や曖昧な点が少ないか、軽微なもの
- medium: 基本的な理解はあるが、一部に曖昧さや不正確な理解がある。重要な概念の一部が抜けている
- low: 重要な概念に誤解がある、または曖昧な点が多い。基礎レベルの復習が必要

### strengths（良かった点）
- ユーザーが正確に理解していた概念を具体的に挙げる
- 「〜について正しく理解できています」ではなく「〜が〜であることを正確に説明できています」のように具体的に
- 分析結果の「正確な理解」に基づく
- **1〜3項目**。各項目は **1文・60〜80字以内**
- 1項目に複数の論点を詰め込まない（読み手が一目で把握できる粒度）
- 中黒「・」や読点での概念列挙で長文化しない。論点が増える場合は項目を分ける

### improvements（改善点）
- 分析結果の「誤解・用語の混同」「曖昧な表現」「未言及の重要概念」に基づいて具体的に指摘する
- 誤解がある場合は、何が間違いで正しくはどうなのかを明示する
  （例:「○○と△△を混同しているようですが、実際には○○は〜であり、△△は〜です」）
- 次回の復習で重点的に確認すべき内容を示す
- **1〜3項目**。各項目は **1〜2文・最大100字程度**
- 1項目=1論点。「例：…」を入れる場合も項目内は1論点に絞る
- 中黒「・」や読点で関連概念を列挙して長文化しない。複数概念を扱う場合は項目を分ける
- 「〜する練習をする」等の同じ語尾の繰り返しを避け、端的に何を見直すかを書く
- 各項目の `aspect_id` には、観点一覧で最も近い観点の id を 1 つ入れる。当たる観点が無ければ空文字。観点名を入れない

## 厳守事項
{{NO_FABRICATION}}
- 評価は分析結果とノートの内容に基づく。推測や一般論で評価しない
- 厳しすぎず甘すぎず、正確な評価を心がける
- ノートの「学んだこと」が空または不十分な場合、strengthsには「対話が不十分なため評価困難」と記載する
- ユーザーが自分の言葉で説明できていない概念を「理解している」と評価しない
- フィードバックは建設的で、ユーザーの学習意欲を維持する表現を使う

## 対話が不十分だった場合の評価
- understanding_level: 必ず "low" とする
- strengths: 「学習トピックに興味を持ち、対話を開始した点」等、事実のみ
- improvements: 基礎概念から学習を始めることを具体的に提案する
"""
)


ASPECT_SECTION = """
## ノートの観点一覧
改善点の `aspect_id` に使う。id は一字一句そのまま書く。
{aspects}
"""

NO_ASPECT_SECTION = """
## ノートの観点一覧
観点一覧はありません。改善点の `aspect_id` は常に空文字にする。
"""


def build_aspect_section(aspect_map: dict[str, Any] | None) -> str:
    lines = [f"{'  ' * ref.depth}- {ref.id}: {ref.name}" for ref in iter_aspects(aspect_map or {"aspects": []})]
    if not lines:
        return NO_ASPECT_SECTION
    return ASPECT_SECTION.format(aspects="\n".join(lines))
