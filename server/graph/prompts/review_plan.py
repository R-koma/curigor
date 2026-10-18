"""復習の質問プランの生成プロンプト（services/review_plan.py 用）。"""

import hashlib
import json
from typing import Any

from graph.aspect_map import iter_aspect_nodes
from graph.output_schemas import ReviewPlanGeneration
from graph.prompts._base import inject_formatting
from graph.review_plan import CarryoverPoint

_NONE = "（なし）"

REVIEW_PLAN_PROMPT = inject_formatting(
    """\
あなたは学習者の復習を設計する専門家です。
ユーザーは以前「{topic}」を学び、下のノートを残しました。次の復習でユーザーに説明してもらう「要点」と、
要点ごとの「質問」を前もって作り、ReviewPlanGeneration スキーマに従って出力してください。

復習の目的は、トピックの重要な内容をユーザーが自分の言葉で説明し直せるかを確かめ、説明できなかった所に気づいてもらうことです。
1 回の復習で聞くのは 4〜5 件です。残りの要点は、ユーザーが重点に選んだ観点に合わせた入れ替えや、次回以降に使います。

## ノートの要約
{summary}

## ノート
<note>
{content}
</note>

## ノートの節の扱い
- 「学んだこと」「重要なポイント」: ユーザーが自分の言葉で説明できた内容
- 「AIの補足」: AI が示したが、ユーザーはまだ自分の言葉で説明していない用語・説明。
  要点にするときの source は ai_supplement
- 「まだ曖昧な点」: ユーザーが理解しきれていない所。要点にするときの source は ambiguous
- 「復習での追記」: 過去の復習でユーザーが説明できた内容・気づき
- 「（記録なし）」とだけ書かれた節からは要点を作らない

## 観点マップ（id: 観点名（coverage）— 学習で扱われた内容）
coverage は covered=説明できた / partial=触れたが理解が浅い / uncovered=学習で触れていない重要な観点
{aspects}

## 前回の改善点
{improvements}

## 引き継ぎの要点（前回までに説明できなかった・聞けなかったもの）
{carryover}

## 直前の復習で聞いた質問（同じ文・同じ聞き方を使わない）
{previous_questions}

## 復習の回数と問いの深さ
完了した復習: {review_count} 回
{depth_stage}
まだ説明できていない引き継ぎの要点は、段階に関わらず要点そのものを説明してもらう問いでよい。

## 要点の選び方
要点には、このトピックを理解したと言えるために欠かせない内容を選ぶ。固有の数値や名前の暗記のような枝葉は選ばない。
次の順に優先する。上の種類で件数が埋まったら、下の種類は減らしてよい。
1. carryover: 引き継ぎの要点。渡されたものは 1 件ずつ必ず含め、carryover_key にそのキー（c1 など）を入れる。
   point は渡された文のまま変えない。question は前回の質問と別の聞き方にする。言い回しを変えるだけでなく、
   理由・具体例・手順・使いどころなど、問う角度を変える
2. improvement: 前回の改善点。1 つの改善点から 1 件。aspect_id は改善点に付いている観点の ID
3. aspect_gap: coverage が partial・uncovered の観点。
   general: ノートにも観点マップにも無いが、このトピックで一般に重要とされる内容
4. ambiguous（ノートの「まだ曖昧な点」）・ai_supplement（ノートの「AIの補足」）
5. covered: coverage が covered の観点を短く確かめ直すもの。1〜2 件

- 引き継ぎを含めて全部で 6〜10 件。出力は上の順に並べ、同じ種類の中ではトピックの理解に重要なものから並べる
- 同じ内容の要点を 2 件作らない。改善点・partial / uncovered の観点・「まだ曖昧な点」が同じ内容を指すときは、
  上の順で先に来る種類の 1 件にまとめる
- 観点マップがあるときは、ルート直下の観点のそれぞれに少なくとも 1 件の要点が当たるようにする（6〜10 件の範囲で）。
  ユーザーは復習の開始時に観点を選んで重点にできるため
- aspect_id: 要点が当たる観点の ID を観点マップからそのまま入れる。子の観点に当たるなら子の ID。
  どれにも当たらなければ空文字

## ノートに無い要点
- ノートに書かれていない要点は in_note=false にする。
  ノートのどこか（「AIの補足」「まだ曖昧な点」を含む）に書かれていれば in_note=true
- ノートに無い要点は、このトピックで広く認められている内容（入門書や公式の資料に載る水準）だけにする。
  新しい動向・異説・細かな数値は使わない。トピックの範囲から外れない
- uncovered の観点や改善点と同じ内容なら、general を新しく作らず、
  その観点・改善点の要点として 1 件にまとめる（in_note=false）
- general は 1〜2 件まで

## 各項目の書き方
- point: ユーザーが説明できればよいことを 1 文で書く。終わった後の一覧でユーザーが読むので、
  何についての内容かが分かるように書く
  （例: 「TCP が届かなかったデータを再送で補う仕組み」）
- question: ユーザーへの問いかけを 1〜2 文で書く
- expected: 説明に入っていてほしいことを 2〜4 個、短い句で書く。対話中の判定・ヒント・正しい説明の材料にし、
  ユーザーには見せない。正しい内容だけを書き、ノートにある要点はノートの記述に沿う

## 質問の決まり
- 説明を求める形にする（「なぜ〜のか説明してください」「〜すると何が起きるか、順を追って説明してください」
  「〜をどんな場面で使うか、例を挙げて説明してください」など）
- はい／いいえで答えられる問いや、用語・名前を言い当てれば済む問い（「〜を何と呼びますか」）を作らない
- 問いの中に、答え・答えになる用語・比べる相手を書かない
  （例: 「A は B と比べてなぜ速いのか」は B を示してしまうので、「A が速い理由を説明してください」にする）
- 1 つの問いで 1 つのことを聞く。「〜とは何か、また〜」のように 2 つを続けない
- 口頭でも 1〜2 分で答えられる大きさにする
- 全体で同じ文型が並ばないよう、「なぜ」「どうなる」「どう使う」「具体例」「手順」「ほかの内容とのつながり」を混ぜる
- 丁寧語で書く。「観点」「改善点」「AIの補足」「引き継ぎ」など、この指示の中の言葉を問いに使わない

{{FORMATTING}}
"""
)

DEPTH_STAGE_BASICS = (
    "今回の段階: 基礎の確認。定義と仕組みを説明してもらう問いを中心にし、"
    "「なぜ」「どう使うか」「ほかの内容とのつながり」を問うものは 2〜3 件にする"
)
DEPTH_STAGE_DEEPENING = (
    "今回の段階: 理解を深める。半分以上の要点で「なぜそうなるか」「どう使うか」「ほかの内容とどうつながるか」を問う。"
    "定義だけを問うのは covered の確認に限る"
)
DEPTH_STAGE_APPLICATION = (
    "今回の段階: 応用とつながり。ほぼすべての要点で、理由・使いどころ・ほかの内容とのつながりを問う。"
    "具体的な場面を示して、どう考えるか・どうするかを説明してもらう問いも入れる。定義だけを問う質問は作らない"
)


def depth_stage(review_count: int) -> str:
    if review_count <= 1:
        return DEPTH_STAGE_BASICS
    if review_count <= 3:
        return DEPTH_STAGE_DEEPENING
    return DEPTH_STAGE_APPLICATION


def _format_aspects(aspect_map: dict[str, Any] | None) -> str:
    lines: list[str] = []
    for ref, node in iter_aspect_nodes(aspect_map or {"aspects": []}):
        coverage = str(node.get("coverage") or "")
        summary = str(node.get("summary") or "").strip()
        line = f"{'  ' * ref.depth}- {ref.id}: {ref.name}"
        if coverage:
            line += f"（{coverage}）"
        if summary:
            line += f"— {summary}"
        lines.append(line)
    return "\n".join(lines) or "（観点マップはありません）"


def _format_improvements(improvements: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in improvements:
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        aspect_id = item.get("aspect_id")
        lines.append(f"- {text}（観点: {aspect_id}）" if aspect_id else f"- {text}")
    return "\n".join(lines) or _NONE


def _format_carryover(carryover: list[CarryoverPoint]) -> str:
    lines: list[str] = []
    for c in carryover:
        head = f"- {c['key']}: {c['point']}"
        if c["aspect_id"]:
            head += f"（観点: {c['aspect_id']}）"
        lines.append(f"{head}\n  前回の質問: {c['question']}")
    return "\n".join(lines) or _NONE


def build_review_plan_prompt(
    *,
    topic: str,
    summary: str,
    content: str,
    aspect_map: dict[str, Any] | None,
    improvements: list[dict[str, Any]],
    carryover: list[CarryoverPoint],
    previous_questions: list[str],
    review_count: int,
) -> str:
    return REVIEW_PLAN_PROMPT.format(
        topic=topic,
        summary=summary.strip() or _NONE,
        content=content,
        aspects=_format_aspects(aspect_map),
        improvements=_format_improvements(improvements),
        carryover=_format_carryover(carryover),
        previous_questions="\n".join(f"- {q}" for q in previous_questions if q.strip()) or _NONE,
        review_count=review_count,
        depth_stage=depth_stage(review_count),
    )


def _review_plan_prompt_fingerprint() -> str:
    parts = [
        REVIEW_PLAN_PROMPT,
        DEPTH_STAGE_BASICS,
        DEPTH_STAGE_DEEPENING,
        DEPTH_STAGE_APPLICATION,
        json.dumps(ReviewPlanGeneration.model_json_schema(), ensure_ascii=False, sort_keys=True),
    ]
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:12]


REVIEW_PLAN_PROMPT_FINGERPRINT = _review_plan_prompt_fingerprint()
