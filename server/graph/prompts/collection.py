"""ノートを束ねるテーマの候補のプロンプト（generate_note 用）。"""

from graph.prompts._base import UNSPECIFIED_PLACEHOLDER

COLLECTION_SUGGESTION_PROMPT = """\
あなたは学習ノートを束ねるテーマを提案する専門家です。
新しく作られたノートを、ユーザーの既存のテーマに入れるか、新しいテーマを作るかを判断し、
CollectionSuggestion スキーマに従って出力してください。

## ノートのトピック
{topic}

## 学習に使った教材（ユーザーの回答）
{source}

## 既存のテーマ
{existing_collections}

## 判断基準
1. ノートが既存のテーマの一部（同じ教材、または同じ大きな主題の一部）なら、そのテーマ名を一字一句そのまま返す
2. 既存のテーマに合わず、教材に書名・講座名など特定の教材の名前があれば、その名前を新しいテーマ名として返す
3. 教材が「書籍」「公式ドキュメント」のような種類だけで、既存のテーマにも合わなければ空文字を返す
4. ノートのトピックそのものをテーマ名にしない
"""


def build_collection_suggestion_prompt(*, topic: str, source: str, existing_collections: list[str]) -> str:
    existing = "\n".join(f"- {name}" for name in existing_collections) or "（まだテーマはありません）"
    return COLLECTION_SUGGESTION_PROMPT.format(
        topic=topic, source=source.strip() or UNSPECIFIED_PLACEHOLDER, existing_collections=existing
    )
