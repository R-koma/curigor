"""失敗モードの正本。

`failure_mode`（golden のファイル名とフィールド）と `first_failure`（jsonl の annotation）は
どちらも自由文字列で、表記ゆれが入ると集計が静かに割れる。ここを唯一の値空間にして
`tests/unit/evals/test_dataset_invariants.py` が強制する。

網羅的な taxonomy を今作らないのは意図的（`README.md` の規約: error analysis が ~100 trace で
saturation してから）。ここは「今ある値を固定し、追加を PR レビューに通す」ためだけにある。
"""

from __future__ import annotations

FAILURE_MODES: dict[str, str] = {
    "note_request_answered_in_chat": (
        "ノート作成の依頼に対し、所定のノート作成処理へ進まず、チャット内の要約で代替する"
    ),
    "ignored_session_end": "学習者がセッションの終了を明示しているのに、終了処理や案内に進まず、学習の質問を続ける",
    "premature_wrap_up": (
        "学習者が終了を望んでおらず、つまずきに応じた支援を十分に試していない段階で、学習の終了・中断を提案する"
    ),
    "abrupt_topic_transition": (
        "学習者の直前の回答とのつながりや、話題を移す案内がなく、別の観点へ唐突に質問を切り替える"
    ),
    "accurate_multi_concept_overexplain": "誤りのない複数観点の列挙に対し、AI が全観点へ解説を被せる",
    "self_answered_question": "AI が自分の質問の答えを同じ応答内で先に述べてしまう",
    "uncorrected_misconception": "訂正を要する誤り・混同を含むユーザー説明を、AI が訂正せず追認して次へ進む",
    "overexplained_correct_content": "誤りのないユーザー説明に、AI が言い直し・補強の解説を被せる",
    "over_deepened_single_aspect": "AI が同じ観点を掘り下げ続け、他の観点へ戻らないまま学習者の知識の外まで降りる",
    "undirected_followup": "AI が「もう少し詳しく」のような定型句で促し、学習者に考える手がかりを渡さない",
    "repeated_answered_question": "学習者が直前に答えた問いを、AI がその回答に触れないままほぼ同じ形で出し直す",
    "preempted_learner_explanation": "AI が、学習者に説明させるべき対比・理由・利点を、問いの前に先に述べてしまう",
    "repetitive_phrasing": "AI が直前までの応答と同じ書き出し・定型句を繰り返す",
    "ignored_learner_question": "学習者の質問・説明の依頼に答えないまま、AI が問いを返す",
    "assumed_unmentioned_concept": (
        "AI が、答えるのに学習者がまだ口にしていない専門的な概念・用語の知識が要る問いを、その説明なしに出す"
        "（日常の経験で答えられる問いは含めない）"
    ),
    "insufficient_unknown_scaffold": (
        "学習者が「わからない」と答えたあと、AI が説明を足しても、次の問いが漠然としていて、"
        "答えるための足場（具体的な状況・小さな問い・選択肢）を渡さない"
    ),
    "monotonous_unknown_support": (
        "学習者が「わからない」と続けたとき、AI が同じ支援の仕方を繰り返すか、同じ問いを言い換えるだけになる"
    ),
    "unclear_question": (
        "AI の問いが、日本語として崩れている、または回りくどく、一度読んだだけでは何を答えればよいかが分からない"
    ),
    "premise_shifting_correction": (
        "学習者が置いた前提の中では正しい説明を、AI が説明していない別の前提を持ち込んで「そうとは限らない」と否定する"
    ),
}

# jsonl レコードの `source`。real = 本番 LLM の実出力、rerun = eval の regression 再実行、
# handwritten = 人が書いた応答（正例の理想応答など）
SOURCES: frozenset[str] = frozenset({"real", "rerun", "handwritten"})

# jsonl レコードの `meta.route`。キーなし = 旧経路（question.py + 事前分析）。
# map = 聞き取り → 深さの地図 → 地図駆動の質問生成
ROUTES: frozenset[str] = frozenset({"map"})
