import hashlib
import json

from graph.output_schemas import ReviewTurnAnalysis

REVIEW_TURN_ANALYSIS_PROMPT = """\
あなたは復習の対話の 1 ターンを分析する専門家です。
ユーザーは「{topic}」を復習しています。直近のユーザー発言が、セッションを終えたいという意志かを判定し、
ReviewTurnAnalysis スキーマに従って出力してください。

## 対話履歴（直近のみ）
{recent_messages}

## 判定
- true: セッションを終えたい、またはノートを更新してほしいと伝えている
  （例: 「今日はここまでにします」「終了してください」「ノートを更新して」）。答えと一緒でも true
- false: 答え・質問・「わかりません」、および答えが尽きただけの発言（例: 「以上です」「他は思い出せません」）
"""


def build_review_turn_analysis_prompt(*, topic: str, recent_messages: str) -> str:
    return REVIEW_TURN_ANALYSIS_PROMPT.format(topic=topic, recent_messages=recent_messages)


def _review_turn_analysis_prompt_fingerprint() -> str:
    parts = [
        REVIEW_TURN_ANALYSIS_PROMPT,
        json.dumps(ReviewTurnAnalysis.model_json_schema(), ensure_ascii=False, sort_keys=True),
    ]
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:12]


REVIEW_TURN_ANALYSIS_PROMPT_FINGERPRINT = _review_turn_analysis_prompt_fingerprint()
