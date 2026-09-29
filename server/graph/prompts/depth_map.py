"""深さの地図の生成プロンプト（聞き取り完了時に1回だけ呼ぶ）。"""

from graph.prompts._base import UNSPECIFIED_PLACEHOLDER, inject_charter

DEPTH_MAP_GENERATION_PROMPT = inject_charter(
    """\
## 役割
あなたはソフトウェア開発者向け学習設計の専門家です。
「{topic}」というトピックについて、学習者が自分の言葉で深く説明できるようになるための
観点（中核となる問いの単位）を設計します。

## 学習者の情報
- 学習ゴール（目的）: {purpose}
- 学習材料の出典: {source}
- 前提知識: {prior_knowledge}

## タスク
トピックを 3〜7 個の観点に分解してください。各観点について:

1. `name`: 観点名（日本語の短い名詞句）
2. `is_core`: 学習ゴールの達成に不可欠な中核観点なら true。中核は最大4個まで。
   目的が「未指定」の場合は、トピックの理解に一般的に不可欠な観点を中核とする
3. `defined_question`: この観点を自分の言葉で定義できるかを問う核心
4. `reasoned_question`: なぜこの仕組みが必要か・どう動くかを問う核心。
   **日常の具体例を挙げさせるだけの問いにしない**。「〜する場面を1つ挙げて」のような
   浅い例示ではなく、「なぜ〇〇ではなく△△という設計になっているのか」
   「〇〇が無いと何が困るのか」のように、必要性や動作原理そのものを問う
5. `applied_question`: 学習ゴールに沿った具体的な活用場面を問う核心。
   学習ゴールが「未指定」の場合は、トピックが実務で使われる一般的な場面を問う

## 厳守事項
{{NO_FABRICATION}}
- 前提知識に含まれる内容は、より深い段階（なぜ・仕組み、応用）から始めてよい
- 出典が分かる場合、その水準・範囲に合わせる（入門書なら基礎観点を厚く、専門書なら発展的観点も含める）
"""
)


def build_depth_map_prompt(*, topic: str, purpose: str, source: str, prior_knowledge: str) -> str:
    return DEPTH_MAP_GENERATION_PROMPT.format(
        topic=topic,
        purpose=purpose or UNSPECIFIED_PLACEHOLDER,
        source=source or UNSPECIFIED_PLACEHOLDER,
        prior_knowledge=prior_knowledge or UNSPECIFIED_PLACEHOLDER,
    )
