import hashlib
import json
from collections.abc import Sequence

from graph.output_schemas import TranscriptionKeywordsDraft
from graph.prompts._base import UNSPECIFIED_PLACEHOLDER

TRANSCRIPTION_KEYWORDS_PROMPT = """\
学習者が「{topic}」について、学んだ内容を声で説明します。音声認識に手がかりとして渡すため、
学習者が説明の中で口にしそうな用語を挙げ、TranscriptionKeywordsDraft スキーマに従って出力してください。

## 学習の情報
- 観点: {aspects}
- 補足: {context}

## 挙げる用語
- このトピックの専門用語・英字の略語・コマンド名・固有名詞（人名・製品名・規格名）
- 音声から文字にするときに誤りやすいもの（同音異義の漢字、カタカナと英字の表記が揺れるもの）を優先する
- 表記は、その分野で一般的に書かれる形にする（例: 英字の略語は英字で「TCP」、漢字の用語は漢字で「輻輳制御」）
- 1 件は 1 語か短い名詞句にし、文や説明は書かない
- 10〜20 件。トピック名と観点名そのものは挙げなくてよい（別に渡す）

## 挙げないもの
- 「仕組み」「説明」「理解」のような、どの分野にも出る一般的な語
- このトピックと関係の薄い語（音声認識が、話していない語に引っ張られる）
"""


def build_transcription_keywords_prompt(*, topic: str, aspects: Sequence[str], context: str) -> str:
    return TRANSCRIPTION_KEYWORDS_PROMPT.format(
        topic=topic,
        aspects="、".join(aspects) or UNSPECIFIED_PLACEHOLDER,
        context=context or UNSPECIFIED_PLACEHOLDER,
    )


def _transcription_keywords_prompt_fingerprint() -> str:
    parts = [
        TRANSCRIPTION_KEYWORDS_PROMPT,
        json.dumps(TranscriptionKeywordsDraft.model_json_schema(), ensure_ascii=False, sort_keys=True),
    ]
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:12]


TRANSCRIPTION_KEYWORDS_PROMPT_FINGERPRINT = _transcription_keywords_prompt_fingerprint()
