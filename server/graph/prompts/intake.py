"""聞き取り（目的・出典・前提知識）のカード・抽出・キックオフのプロンプト（learning_start / _intake.py 用）。"""

import hashlib

from graph.prompts._base import inject_charter
from graph.prompts.depth_map import build_depth_map_prompt

INTAKE_CARD_PROMPT = inject_charter(
    """\
あなたは学習セッション開始前の聞き取りカードを準備する専門家です。
ユーザーが学習を始めるときの最初の発言から、IntakeCardDraft スキーマに従って構造化して出力してください。

## ユーザーの最初の発言
{utterance}

## タスク
1. `topic_is_clear`: 発言だけで学ぶ対象が一意に決まるなら true。「この仕組み」「それ」のように指示語だけで
   対象が分からない、「基礎から学びたい」のように対象が書かれていない場合は false。会話の文脈や教材が
   手元にあるとは仮定せず、発言の文面だけで判断する
2. `topic`: 発言が指す学習トピックを短い名詞句にする。目的・動機・「学びたい」などの依頼表現は除く。
   `topic_is_clear` が false のときは、発言から読み取れる範囲の仮の名詞句にとどめ、対象を補って作らない
3. `topic_candidates`: `topic_is_clear` が false のとき、発言に書かれた言葉から無理なく推せる学習トピックの
   候補を0〜3件。手がかりが無ければ空のリスト。true のときは空のリスト
4. `purpose_options`: このトピックを学ぶ目的としてありそうなものを3〜4件。発言に目的が明示されていれば、
   その目的を発言の言い回しに近いラベルで必ず含める
5. `source_options`: このトピックの学習材料としてありそうな種類を3〜4件。特定の書名は、発言に出てきた場合だけ使う
6. `inferred_purpose`: 発言に目的が明示されていれば、4 で含めたそのラベル。無ければ空文字

## 厳守事項
{{NO_FABRICATION}}
"""
)

LEARNING_KICKOFF_PROMPT = inject_charter(
    """\
## 役割
あなたはフレンドリーで傾聴力のある優秀なメンターです。常にユーザーの目線で寄り添うことを心がけてください。

## トピック
{topic}

## 聞き取りで分かったこと
- 目的（何ができるようになりたいか）: {purpose}
- 学習材料の出典: {source}
- 前提知識（今何を知っているか）: {prior_knowledge}

## 対話履歴（直近のみ）
{recent_messages}

## タスク
聞き取りを終えて学習を始める合図として、短い声かけを1回だけ返してください。
ユーザーが教材を読み進めながら、理解したことを自分の言葉で説明し始められるよう促します。

## ルール
- 聞き取りを終えて、ここから学習を始めることを伝える
- 「聞き取りで分かったこと」のうち回答のある項目だけを、1文で受け止める。「未回答」の項目には触れない
- 出典があれば「〇〇を読み進めながら」と添え、なければ「学んだことを」と促す
- 理解したことを自分の言葉で説明してほしいこと、断片的でも構わないことを伝える
- トピックの内容に踏み込まない。定義・仕組み・例の提示も、「〜とは何か」「なぜ〜か」のような問いも出さない
- 質問は出さない。説明の促しだけにする
- 日本語で、2〜3文で応答する
- 「正しい」「間違い」のような評価はしない

## 例（出典と前提知識のみ回答あり、目的は未回答）
AI: 「ありがとうございます。『Linuxのしくみ』で、ほとんど知らないところから学ぶのですね。
     ここから学習を始めましょう。読み進めながら、理解できたことを自分の言葉で説明してみてください。
     断片的でも大丈夫です。」
"""
)

INTAKE_EXTRACTION_PROMPT = inject_charter(
    """\
あなたは学習セッション開始前の聞き取りを分析する専門家です。
ユーザーが「{topic}」を学ぼうとしています。直近のユーザー発言から、
IntakeExtraction スキーマに従って構造化して出力してください。

## これまでに分かっていること
- 目的: {purpose}
- 学習材料の出典: {source}
- 前提知識: {prior_knowledge}

## 対話履歴（直近のみ）
{recent_messages}

## タスク
`purpose` / `source` / `prior_knowledge`: 直近のユーザー発言に新しい情報があれば抽出する。
言及が無い項目は空文字。「これまでに分かっていること」に既にある内容の言い換えは抽出しない
{topic_task}

## 厳守事項
{{NO_FABRICATION}}
"""
)


TOPIC_EXTRACTION_TASK = (
    "`topic`: 現在のトピックは最初の発言だけでは定まらなかった仮の値で、聞き取りでユーザーに確かめている。"
    "直近のユーザー発言で学ぶ対象が具体的に示されていれば、短い名詞句（30字以内。目的・「学びたい」などの"
    "依頼表現は除く）にして抽出する。示されていなければ空文字"
)


def _known(value: str) -> str:
    return value or "未回答"


def build_intake_extraction_prompt(
    *,
    topic: str,
    purpose: str,
    source: str,
    prior_knowledge: str,
    recent_messages: str,
    confirm_topic: bool = False,
) -> str:
    return INTAKE_EXTRACTION_PROMPT.format(
        topic=topic,
        topic_task=TOPIC_EXTRACTION_TASK if confirm_topic else "",
        purpose=_known(purpose),
        source=_known(source),
        prior_knowledge=_known(prior_knowledge),
        recent_messages=recent_messages or "（まだなし）",
    )


def build_learning_kickoff_prompt(
    *, topic: str, purpose: str, source: str, prior_knowledge: str, recent_messages: str
) -> str:
    return LEARNING_KICKOFF_PROMPT.format(
        topic=topic,
        purpose=_known(purpose),
        source=_known(source),
        prior_knowledge=_known(prior_knowledge),
        recent_messages=recent_messages or "（まだなし）",
    )


def build_intake_card_prompt(*, utterance: str) -> str:
    return INTAKE_CARD_PROMPT.format(utterance=utterance)


def _intake_prompt_fingerprint() -> str:
    """セッション開始面（聞き取りカード・抽出・声かけ・深さの地図生成）の内容ハッシュ。"""
    parts = [
        build_intake_card_prompt(utterance="U"),
        build_intake_extraction_prompt(topic="T", purpose="", source="S", prior_knowledge="", recent_messages=""),
        build_intake_extraction_prompt(
            topic="T", purpose="", source="S", prior_knowledge="", recent_messages="", confirm_topic=True
        ),
        build_learning_kickoff_prompt(topic="T", purpose="", source="S", prior_knowledge="", recent_messages="M"),
        build_depth_map_prompt(topic="T", purpose="", source="S", prior_knowledge=""),
    ]
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:12]


INTAKE_PROMPT_FINGERPRINT = _intake_prompt_fingerprint()
