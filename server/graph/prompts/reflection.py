import hashlib
from dataclasses import dataclass
from datetime import date
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


@dataclass(frozen=True)
class PeriodWording:
    label: str
    opening: str


def period_wording(period: Period, start: date, *, current: bool) -> PeriodWording:
    if current:
        if period == "day":
            return PeriodWording(label="今日", opening="あなたは今日〇〇を学習しました。")
        return PeriodWording(label="今週", opening="今週は〇〇を学習しました。")
    md = f"{start.month}月{start.day}日"
    if period == "day":
        return PeriodWording(label=f"{md}に", opening=f"{md}は〇〇を学習しました。")
    return PeriodWording(label=f"{md}の週に", opening=f"{md}の週は〇〇を学習しました。")


REFLECTION_QUIZ_PROMPT = """あなたは学習アプリの出題役です。利用者が{period_label}学んだ内容から、
理解を確かめる 4 択の小テストを作ってください。

# 振り返りの内容
{reflection}

# 作り方
- 3〜5 問にする
- 「つまずいた所」と「疑問」に挙がった内容を優先して出題する。足りなければ、学んだトピックの要点から出す
- 選択肢はちょうど 4 つ。誤答は、よくある勘違いなど、もっともらしいものにする
- 正解は 1 つだけにし、正解の位置は問ごとにばらす
- 解説は 1〜2 文で、なぜその答えになるかを書く
- 上の内容に無いことは出題しない
"""


def build_reflection_script_prompt(*, wording: PeriodWording, reflection: str, max_chars: int) -> str:
    return REFLECTION_SCRIPT_PROMPT.format(
        period_label=wording.label,
        reflection=reflection,
        opening=wording.opening,
        max_chars=max_chars,
    )


def build_reflection_quiz_prompt(*, wording: PeriodWording, reflection: str) -> str:
    return REFLECTION_QUIZ_PROMPT.format(period_label=wording.label, reflection=reflection)


def _fingerprint(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:12]


REFLECTION_SCRIPT_PROMPT_FINGERPRINT = _fingerprint(REFLECTION_SCRIPT_PROMPT)
REFLECTION_QUIZ_PROMPT_FINGERPRINT = _fingerprint(REFLECTION_QUIZ_PROMPT)
