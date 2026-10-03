"""テーマのまとめの下書きのプロンプト（services/collection_synthesis.py 用）。"""

import hashlib

from graph.prompts._base import inject_charter
from graph.state import SynthesisConnectionState

SYNTHESIS_DRAFT_PROMPT = """\
あなたは学習者のノートを束ねて、テーマ全体のまとめを作る編集者です。
次のノートはすべて、ユーザーが「{collection_name}」というテーマで学んだ記録です。
SynthesisDraftOutput スキーマに従って出力してください。

## ノート
{notes_block}

## タスク
1. `content`: テーマ全体のまとめを Markdown で書く。ノートの順番をなぞらず、テーマの構成に沿って見出しを立てる。
   各段落の末尾に、根拠にしたノートのラベルを `[N1]` の形で付ける（複数なら `[N1][N3]`）
2. `connections`: 別々のノートに書かれた内容どうしの関係のうち、テーマの理解に重要なものを重要な順に最大5件
3. `contradictions`: ノートどうしで説明が食い違っている箇所。無ければ空
4. `gaps`: このテーマを理解するうえで重要なのに、どのノートにも書かれていない領域を最大5件

## 厳守事項
- `content` と `connections` には、ノートに書かれている内容だけを使う。ノートに無い知識を足さない
- `gaps` だけは、ノートに無い領域を挙げてよい
- ラベルはノートの見出しに付いているものだけを使う
- `question` には答えやヒントを含めない
"""


def build_synthesis_draft_prompt(*, collection_name: str, notes_block: str) -> str:
    return SYNTHESIS_DRAFT_PROMPT.format(collection_name=collection_name, notes_block=notes_block)


SYNTHESIS_OPENING_PROMPT = """\
## 役割
あなたは、学習者が自分のノートどうしのつながりを自分の言葉で説明できるよう手伝うメンターです。

## テーマ
{collection_name}

## 指示
学習者に、このテーマのノートどうしのつながりを{total}つ順に説明してもらうことを一言で伝え、
次の1つ目の問いをそのまま聞いてください。全体で100字程度に収め、答えやヒントは言わないでください。

## 1つ目のつながり
{first_section}
"""

SYNTHESIS_DIALOGUE_PROMPT = """\
## 役割
あなたは、学習者が自分のノートどうしのつながりを自分の言葉で説明できるよう手伝うメンターです。

## テーマ
{collection_name}

## 学習者のノート
{notes}

## 進め方
学習者に、ノートどうしのつながりを1つずつ説明してもらっています（全部で{total}つ）。

## 直前に聞いたつながり
{current_section}

## 次に聞くつながり
{next_section}

## 指示
1. 直前に聞いたつながりがあれば、学習者の最後の発言を「参考の説明」と照らし合わせ、合っている点を1文で認める
2. 誤りや抜けがあれば、どこが違うかを短く伝え、ノートの内容に沿って正す。参考の説明をそのまま読み上げない
3. 次に聞くつながりがあれば、その問いをそのまま聞く。無ければ、全部聞き終えたことを伝え、
   画面の終了ボタンで説明をまとめに反映できると案内する
4. 直前に聞いたつながりも次に聞くつながりも無ければ、学習者の発言に短く答え、終了ボタンを案内する
5. 全体で200字程度に収める。問いは1つだけにする
"""

SYNTHESIS_INSIGHTS_PROMPT = inject_charter(
    """\
次の会話で、学習者はノートどうしのつながりを説明しました。
SynthesisInsightsOutput スキーマに従い、つながりごとに学習者の説明を整理してください。

## つながり
{connections}

## 会話
{conversation}

## 指示
- 学習者が説明したつながりごとに1件出力する。`connection_id` は上の id をそのまま使う
- 学習者が「わからない」と答えた、または答えずに次へ進んだつながりは出力しない

## 厳守事項
{{NO_FABRICATION}}
"""
)


def _connection_section(connection: SynthesisConnectionState | None, *, with_reference: bool) -> str:
    if connection is None:
        return "なし"
    section = f"- つながり: {connection['title']}\n- 問い: {connection['question']}"
    if with_reference:
        section += f"\n- 参考の説明: {connection['explanation']}"
    return section


def build_synthesis_opening_prompt(*, collection_name: str, total: int, first: SynthesisConnectionState) -> str:
    return SYNTHESIS_OPENING_PROMPT.format(
        collection_name=collection_name,
        total=total,
        first_section=_connection_section(first, with_reference=False),
    )


def build_synthesis_dialogue_prompt(
    *,
    collection_name: str,
    notes: str,
    total: int,
    current: SynthesisConnectionState | None,
    next_connection: SynthesisConnectionState | None,
) -> str:
    return SYNTHESIS_DIALOGUE_PROMPT.format(
        collection_name=collection_name,
        notes=notes,
        total=total,
        current_section=_connection_section(current, with_reference=True),
        next_section=_connection_section(next_connection, with_reference=False),
    )


def build_synthesis_insights_prompt(*, connections: list[SynthesisConnectionState], conversation: str) -> str:
    listed = "\n".join(f"- {c['id']}: {c['title']}" for c in connections)
    return SYNTHESIS_INSIGHTS_PROMPT.format(connections=listed, conversation=conversation)


def _synthesis_prompt_fingerprint() -> str:
    parts = [SYNTHESIS_DRAFT_PROMPT, SYNTHESIS_OPENING_PROMPT, SYNTHESIS_DIALOGUE_PROMPT, SYNTHESIS_INSIGHTS_PROMPT]
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:12]


SYNTHESIS_PROMPT_FINGERPRINT = _synthesis_prompt_fingerprint()
