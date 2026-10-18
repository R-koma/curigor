import hashlib
import json
from collections.abc import Sequence

from graph.output_schemas import ReviewTurnAnalysis
from graph.review_progress import ReviewPointState

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

REVIEW_TURN_CURRENT_POINT_SECTION = """
## 今の要点
直前の AI が質問やヒントで、ユーザーに説明を求めている要点です。
- 要点: {point}
- 説明に入っていてほしいこと: {expected}

current_point_explained: 直近のユーザー発言が今の要点を説明できていれば true。
説明に入っていてほしいことの大半が、言い回しは違っても意味として入っていれば説明できているとみなす。
「わかりません」・的外れ・一部だけの説明・質問を返しただけなら false
"""

REVIEW_TURN_PENDING_POINTS_SECTION = """
## まだ確かめていない要点
{points}

explained_point_ids: 直近のユーザー発言が、上の要点のどれかも説明できていれば、その ID（行頭の p1 など）を入れる。
基準は今の要点と同じ（説明に入っていてほしいことの大半が意味として入っている）。触れただけのものは入れない。無ければ空
"""


def _expected(point: ReviewPointState) -> str:
    return "、".join(point["expected"])


def build_review_turn_analysis_prompt(
    *,
    topic: str,
    recent_messages: str,
    current_point: ReviewPointState | None = None,
    pending_points: Sequence[ReviewPointState] = (),
) -> str:
    prompt = REVIEW_TURN_ANALYSIS_PROMPT.format(topic=topic, recent_messages=recent_messages)
    if current_point is not None:
        prompt += REVIEW_TURN_CURRENT_POINT_SECTION.format(
            point=current_point["point"], expected=_expected(current_point)
        )
    if pending_points:
        lines = "\n".join(
            f"- {p['id']}: {p['point']}（説明に入っていてほしいこと: {_expected(p)}）" for p in pending_points
        )
        prompt += REVIEW_TURN_PENDING_POINTS_SECTION.format(points=lines)
    return prompt


def _review_turn_analysis_prompt_fingerprint() -> str:
    parts = [
        REVIEW_TURN_ANALYSIS_PROMPT,
        REVIEW_TURN_CURRENT_POINT_SECTION,
        REVIEW_TURN_PENDING_POINTS_SECTION,
        json.dumps(ReviewTurnAnalysis.model_json_schema(), ensure_ascii=False, sort_keys=True),
    ]
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:12]


REVIEW_TURN_ANALYSIS_PROMPT_FINGERPRINT = _review_turn_analysis_prompt_fingerprint()
