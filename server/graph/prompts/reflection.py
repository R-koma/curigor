import hashlib
from typing import Literal

REFLECTION_SCRIPT_PROMPT = """あなたは学習アプリの読み上げ役です。利用者が{period_label}学んだ内容を、
本人に語りかける読み上げ原稿にしてください。

# 振り返りの内容
{reflection}

# 書き方
- 最初の文は「{opening}」で始め、続けて学んだトピックを挙げる
- トピックごとに、要点を 1〜2 文で述べる
- 「つまずいた所」「疑問と答え」があれば、責める調子にならないよう軽く触れる
- 上の内容に無いことは足さない
- 耳で聞いて分かる、やさしい話し言葉にする。記号・箇条書き・Markdown は使わない
- 1〜2 分で読める長さ（全体で 600 字前後、多くても 900 字以内）にする
- 1 文は 1 つの考えにとどめ、{max_chars} 字以内にする。原稿は文ごとに分けて返す
"""

Period = Literal["day", "week"]

_PERIOD_LABELS: dict[Period, str] = {"day": "今日", "week": "今週"}


def build_reflection_script_prompt(*, period: Period, reflection: str, max_chars: int) -> str:
    label = _PERIOD_LABELS[period]
    return REFLECTION_SCRIPT_PROMPT.format(
        period_label=label,
        reflection=reflection,
        opening=f"あなたは{label}〇〇を学習しました。",
        max_chars=max_chars,
    )


def _reflection_prompt_fingerprint() -> str:
    return hashlib.sha256(REFLECTION_SCRIPT_PROMPT.encode()).hexdigest()[:12]


REFLECTION_SCRIPT_PROMPT_FINGERPRINT = _reflection_prompt_fingerprint()
