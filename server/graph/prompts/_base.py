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

DETAILED_DIAGRAM_RULE = (
    "- 流れ・構造・関係は、文だけで説明せず ```mermaid の図にする。図は説明に要るだけ使ってよい。"
    "図の前に何を表す図かを1文で示し、図の後に図の要点を1〜2文で説明する"
)

RECORD_RULE = "- 学習者が対話で書いたコードや式は、言い換えて文章にせず、そのまま残す"

CHAT_STRUCTURE_RULES = """\
- 3 文以内の短い返答は、空行も箇条書きも使わずにそのまま書く
- それより長い説明（訂正・ヒント・答えの提示・疑問への回答など）は、話の切れ目ごとに空行を入れて段落を分ける
- 長い説明で 3 つ以上並ぶ要素は箇条書き、手順や順序のあるものは番号リストにする
- 長い説明では、要となる用語だけを **太字** にする（1 回の返答で 1〜3 か所まで）
- 長い説明の後の問いかけは、空行を挟んで最後の段落に置く
- 見出し（`#`）は使わない"""

DETAILED_STRUCTURE_RULES = """\
- 数文で足りる短い答えは、空行も箇条書きも見出しも使わずにそのまま書く
- それより長い説明は、話題ごとに `##` の見出しで分ける。見出しの下をさらに分けるときだけ `###` を使う。`#` は使わない
- 見出しの中は、話の切れ目ごとに空行を入れて段落を分ける
- 2 つ以上のものを複数の点で比べるときは表にする
- 3 つ以上並ぶ要素は箇条書き、手順や順序のあるものは番号リストにする。各項目は語だけにせず、それが何かを文で説明する
- 要となる用語は **太字** にする"""


def inject_formatting(
    template: str,
    *,
    diagrams: bool = False,
    record: bool = False,
    chat: bool = False,
    detailed: bool = False,
) -> str:
    if detailed:
        rules = [FORMATTING_RULES, DETAILED_DIAGRAM_RULE, DETAILED_STRUCTURE_RULES]
        return template.replace("{{FORMATTING}}", "\n".join(rules))
    rules = [FORMATTING_RULES, DIAGRAM_RULE if diagrams else NO_DIAGRAM_RULE]
    if record:
        rules.append(RECORD_RULE)
    if chat:
        rules.append(CHAT_STRUCTURE_RULES)
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
