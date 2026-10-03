"""テーマのまとめの下書きのプロンプト（services/collection_synthesis.py 用）。"""

import hashlib

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


def _synthesis_prompt_fingerprint() -> str:
    parts = [SYNTHESIS_DRAFT_PROMPT]
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:12]


SYNTHESIS_PROMPT_FINGERPRINT = _synthesis_prompt_fingerprint()
