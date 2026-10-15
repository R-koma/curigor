"""プロンプト共通の定数・ヘルパー。

各プロンプトモジュールから参照される横断的な要素のみを置く。
個別タスクのプロンプト本文はタスク別モジュール側に持つ。
"""

from collections.abc import Sequence

from graph.state import RelatedNote

UNSPECIFIED_PLACEHOLDER = "未指定"

NO_FABRICATION_CHARTER = """\
- ユーザーが対話の中で実際に発言・説明した内容のみを扱う
- ユーザーが発言していない知識を推測・補完しない
- AI が説明した内容を「ユーザーが理解した」として扱わない
- ユーザーが「わかりません」と回答した場合、それは「理解していない」事実として記録する"""


def inject_charter(template: str) -> str:
    """`{{NO_FABRICATION}}` プレースホルダを共通の捏造禁止憲章で置換する。"""
    return template.replace("{{NO_FABRICATION}}", NO_FABRICATION_CHARTER)


FORMATTING_RULES = """\
## 表記
- プログラム・コマンド・設定ファイルは ```言語名 のフェンスで囲む。文中の短い識別子やコマンドは `…` で囲む
- 数式は LaTeX で書く。文中は $…$、独立させる式は $$…$$。数値と単位だけなら普通の文で書いてよい
- 計算量の $O(n^2)$ や添字の $x_1$ も数式として $ で囲む
- 金額のドル記号は \\$ と書く（例: \\$5）。$ を通貨の意味で裸のまま使わない
- 学習者が書いたコードや式を引用するときは、中身を変えずに、上のルールどおり `…`・フェンス・$…$ で囲んで使う"""

NO_DIAGRAM_RULE = "- 図は使わない"

DIAGRAM_RULE = (
    "- 流れ・構造・関係を文だけでは伝えにくいときに限り、```mermaid の図を1つまで使ってよい。"
    "図の後に、図の要点を1〜2文で説明する"
)

RECORD_RULE = "- 学習者が対話で書いたコードや式は、言い換えて文章にせず、そのまま残す"


def inject_formatting(template: str, *, diagrams: bool = False, record: bool = False) -> str:
    rules = [FORMATTING_RULES, DIAGRAM_RULE if diagrams else NO_DIAGRAM_RULE]
    if record:
        rules.append(RECORD_RULE)
    return template.replace("{{FORMATTING}}", "\n".join(rules))


def format_learning_plan_fields(
    learning_goal: str | None,
    focus_aspects: list[str] | None,
) -> dict[str, str]:
    """学習プラン情報を聞き取り・質問生成プロンプトに渡す形に整形する。

    `learning_goal` / `focus_aspects` は未入力可で、その場合はプレースホルダを入れる。
    """
    if isinstance(learning_goal, str) and learning_goal.strip():
        goal_text = learning_goal.strip()
    else:
        goal_text = UNSPECIFIED_PLACEHOLDER

    if focus_aspects:
        aspects_text = "\n  - " + "\n  - ".join(focus_aspects)
    else:
        aspects_text = UNSPECIFIED_PLACEHOLDER

    return {
        "learning_goal": goal_text,
        "focus_aspects": aspects_text,
    }


def format_related_notes(notes: Sequence[RelatedNote]) -> str:
    return "\n".join(f"- {n['topic']}: {n['summary']}" if n["summary"] else f"- {n['topic']}" for n in notes)
