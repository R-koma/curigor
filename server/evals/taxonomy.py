"""失敗モードの正本。

`failure_mode`（golden のファイル名とフィールド）と `first_failure`（jsonl の annotation）は
どちらも自由文字列で、表記ゆれが入ると集計が静かに割れる。ここを唯一の値空間にして
`tests/unit/evals/test_dataset_invariants.py` が強制する。

網羅的な taxonomy を今作らないのは意図的（`README.md` の規約: error analysis が ~100 trace で
saturation してから）。ここは「今ある値を固定し、追加を PR レビューに通す」ためだけにある。
"""

from __future__ import annotations

FAILURE_MODES: dict[str, str] = {
    "accurate_multi_concept_overexplain": "誤りのない複数観点の列挙に対し、AI が全観点へ解説を被せる",
    "self_answered_question": "AI が自分の質問の答えを同じ応答内で先に述べてしまう",
    "uncorrected_misconception": "訂正を要する誤り・混同を含むユーザー説明を、AI が訂正せず追認して次へ進む",
    "overexplained_correct_content": "誤りのないユーザー説明に、AI が言い直し・補強の解説を被せる",
    "over_deepened_single_aspect": "AI が同じ観点を掘り下げ続け、他の観点へ戻らないまま学習者の知識の外まで降りる",
    "undirected_followup": "AI が「もう少し詳しく」のような定型句で促し、学習者に考える手がかりを渡さない",
    "repeated_answered_question": "学習者が直前に答えた問いを、AI がその回答に触れないままほぼ同じ形で出し直す",
    "preempted_learner_explanation": "AI が、学習者に説明させるべき対比・理由・利点を、問いの前に先に述べてしまう",
}

# jsonl レコードの `source`。real = 本番 LLM の実出力、rerun = eval の regression 再実行、
# handwritten = 人が書いた応答（正例の理想応答など）
SOURCES: frozenset[str] = frozenset({"real", "rerun", "handwritten"})

# jsonl レコードの `meta.route`。キーなし = 旧経路（question.py + 事前分析）。
# map = 聞き取り → 深さの地図 → 地図駆動の質問生成。再生（regression）は未対応
ROUTES: frozenset[str] = frozenset({"map"})
