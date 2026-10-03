from typing import Literal

from pydantic import BaseModel, Field

ResponseMode = Literal["reinforce", "expand", "deepen"]


class NoteContent(BaseModel):
    topic: str = Field(..., description="学習トピック")
    content: str = Field(..., description="ノート本文")
    summary: str = Field(..., description="ノート要約")


class ReviewAddendum(BaseModel):
    content: str = Field(
        ...,
        description="復習で新たに深まった/判明した点だけをまとめた追記（Markdown 箇条書き）。既存ノート本文は含めない",
    )


class NoteCategory(BaseModel):
    category: str = Field(
        ...,
        description="ノートを分類するカテゴリー名（短い名詞句）。既存カテゴリーに意味的に合致するものがあればそれを再利用する",
    )


class CollectionSuggestion(BaseModel):
    name: str = Field(
        "",
        description="ノートを入れるテーマ名。既存のテーマに入れるならその名前を一字一句そのまま、"
        "新しいテーマなら教材の名前。どちらにも当たらなければ空文字",
    )


class AspectNode(BaseModel):
    name: str = Field(..., description="観点名（短い名詞句）")
    summary: str = Field(..., description="この観点について対話で扱われた内容の1〜2文要約")
    coverage: Literal["covered", "partial", "uncovered"] = Field(
        ...,
        description="対話でのカバー度。covered=ユーザーが自分の言葉で説明できた / "
        "partial=触れたが理解が浅い・曖昧 / uncovered=言及なし（重要な隣接観点として明示）",
    )
    children: list["AspectNode"] = Field(
        default_factory=list,
        description="サブ観点。最大 2 階層まで（ルート→子→孫）。それ以上深くしない",
    )


class AspectMap(BaseModel):
    root: str = Field(..., description="トピック名（ノートの topic と一致させる）")
    aspects: list[AspectNode] = Field(
        ...,
        description="ルート直下の観点リスト。3〜7 項目を目安に、対話で実際に扱われた観点を中心に構成する",
    )


class FeedbackOutput(BaseModel):
    understanding_level: Literal["low", "medium", "high"] = Field(..., description="ユーザーの回答から理解度を算出")
    strength: list[str] = Field(..., description="良かった点")
    improvement_points: list[str] = Field(..., description="改善点")


class AspectObservation(BaseModel):
    aspect: str = Field(
        ...,
        description="観点名（日本語の短い名詞句。英語・ローマ字にしない）。"
        "カバー済み観点一覧に同じ観点があれば同じ表記を再利用する（表記ゆれで別観点にしない）",
    )
    reached_depth: Literal["mentioned", "defined", "exemplified", "applied"] = Field(
        ...,
        description="直近のユーザー発言でこの観点が到達した深さ。mentioned=名前を挙げただけ / "
        "defined=定義を自分の言葉で述べた / exemplified=具体例または動作原理まで述べた / "
        "applied=応用場面・他概念との関係・トレードオフまで述べた",
    )


class DialogueTurnAnalysis(BaseModel):
    """学習対話 1 ターンの事前分析（learning_dialogue の応答生成前に生成される構造化データ）。"""

    observations: list[AspectObservation] = Field(
        default_factory=list,
        description="直近のユーザー発言で言及・説明された観点と到達度。ユーザーが実際に発言した内容のみから判定する",
    )
    # 誤りの判定を response_mode より前に置く。structured output は宣言順に値を埋めるので、
    # この順序がモードを決める前に誤りを見ることを強制する（後ろに置くと深さだけでモードが決まる）
    has_misconception: bool = Field(
        ...,
        description="直近のユーザー発言に、訂正を要する誤り・混同が含まれるか。"
        "手段と結果の取り違え、問いの一部だけで全体に答える、別概念の説明を当てる等を含む。"
        "説明が浅い・言葉足らずなだけで内容が正しいものは誤りに含めない",
    )
    error_summary: str = Field(
        "",
        description="has_misconception が true のとき、誤りの内容を1文で。false のときは空文字",
    )
    response_mode: ResponseMode = Field(
        ...,
        description="次の AI 応答のモード。has_misconception が true なら必ず reinforce。"
        "false のときだけ deepen / expand を深さで選ぶ。"
        "reinforce=誤り・混同の訂正 / "
        "deepen=単一観点の説明が目標レベルに未達なので深掘り / "
        "expand=直近の説明が十分なので別観点へ展開または選んだ観点を深める",
    )
    selected_aspect: str = Field(
        ...,
        description="次の応答で焦点を当てる観点を1つ。日本語の短い名詞句で、observations と同じ表記を使う",
    )


class DialogueAnalysis(BaseModel):
    """対話分析結果（generate_feedback の前段で生成される構造化データ）。"""

    accurate_understanding: list[str] = Field(
        default_factory=list,
        description="ユーザーが正しく理解・説明できている概念。各項目は1文で具体的に",
    )
    misconceptions: list[str] = Field(
        default_factory=list,
        description="誤解・用語の混同。「○○と△△を混同している」「○○を△△の意味で使っている」のように具体的に",
    )
    ambiguous_expressions: list[str] = Field(
        default_factory=list,
        description="曖昧な表現。何が曖昧で、正確にはどう表現すべきかを示す",
    )
    unmentioned_concepts: list[str] = Field(
        default_factory=list,
        description="このトピックで言及されるべきだが触れられていない概念",
    )
    depth_level: Literal["surface", "principle", "applied"] = Field(
        ...,
        description="理解の深さ。surface=表面的な暗記 / principle=原理の理解 / applied=応用レベル",
    )

    def to_markdown(self) -> str:
        def _fmt(items: list[str]) -> str:
            return "\n".join(f"- {x}" for x in items) if items else "- （該当なし）"

        depth_label = {"surface": "表面的な暗記", "principle": "原理の理解", "applied": "応用レベル"}[self.depth_level]
        return (
            f"### 正確な理解\n{_fmt(self.accurate_understanding)}\n\n"
            f"### 誤解・用語の混同\n{_fmt(self.misconceptions)}\n\n"
            f"### 曖昧な表現\n{_fmt(self.ambiguous_expressions)}\n\n"
            f"### 未言及の重要概念\n{_fmt(self.unmentioned_concepts)}\n\n"
            f"### 理解の深さ\n- {depth_label}"
        )


class IntakeExtraction(BaseModel):
    """学習開始前の聞き取り1ターンの構造化抽出。"""

    purpose: str = Field("", description="今回の学習で達成したいこと。直近のユーザー発言に言及が無ければ空文字")
    source: str = Field("", description="学習材料の出典（書籍名・講座名等）。言及が無ければ空文字")
    prior_knowledge: str = Field("", description="トピックについて今何を知っているか。言及が無ければ空文字")


class IntakeOptionDraft(BaseModel):
    label: str = Field(..., description="選択肢の短いラベル（20字以内）")
    description: str = Field("", description="ラベルの補足（30字以内）。不要なら空文字")


class IntakeCardDraft(BaseModel):
    topic: str = Field(..., description="学習トピックの短い名詞句（30字以内）。発言中の目的・動機・依頼表現は含めない")
    purpose_options: list[IntakeOptionDraft] = Field(
        ..., description="このトピックを学ぶ目的としてありそうな選択肢を3〜4件。互いに重ならないこと"
    )
    source_options: list[IntakeOptionDraft] = Field(
        ..., description="このトピックの学習材料としてありそうな種類を3〜4件（書籍・公式ドキュメント・講座など）"
    )
    inferred_purpose: str = Field(
        "",
        description="発言に目的が明示されていれば、purpose_options のうち該当する label をそのまま入れる。"
        "無ければ空文字",
    )


class DepthMapAspectDraft(BaseModel):
    name: str = Field(..., description="観点名（日本語の短い名詞句）")
    is_core: bool = Field(..., description="学習ゴールの達成に不可欠な中核観点か")
    defined_question: str = Field(..., description="「定義」段階で問うべき核心（自分の言葉で定義できるか）")
    reasoned_question: str = Field(
        ...,
        description="「なぜ・仕組み」段階で問うべき核心。日常の具体例ではなく、必要性や動作原理そのものを問う",
    )
    applied_question: str = Field(
        ..., description="「目的に沿った応用」段階で問うべき核心。学習ゴールと結びつけた具体的な活用場面"
    )


class DepthMapGeneration(BaseModel):
    aspects: list[DepthMapAspectDraft] = Field(..., description="3〜7件。中核観点は最大4件まで")


class MapAspectObservation(BaseModel):
    aspect_id: str = Field(
        ...,
        description="言及・説明された観点の id。地図に無い新しい観点なら、id の代わりに"
        "分かりやすい仮の名前（日本語可）を入れてよい。コード側で正式な id に変換する",
    )
    reached_stage: Literal["mentioned", "defined", "reasoned", "applied"] = Field(
        ...,
        description="直近のユーザー発言でこの観点が到達した段階。mentioned=名前のみ / "
        "defined=定義を自分の言葉で述べた / reasoned=なぜ必要か・どう動くかを述べた"
        "（日常の具体例を1つ挙げただけでは reasoned にしない）/ "
        "applied=学習ゴールに沿った具体的な活用場面まで述べた",
    )


class MapDialogueTurnAnalysis(BaseModel):
    """地図駆動の学習対話 1 ターンの事前分析。DialogueTurnAnalysis の地図版。"""

    observations: list[MapAspectObservation] = Field(default_factory=list)
    has_misconception: bool = Field(..., description="直近のユーザー発言に、訂正を要する誤り・混同が含まれるか")
    error_summary: str = Field("", description="has_misconception が true のとき、誤りの内容を1文で")
    response_mode: ResponseMode = Field(..., description="次の AI 応答のモード")
    selected_aspect_id: str = Field(
        ..., description="次の応答で焦点を当てる観点の id。observations と同じ解決規則に従う"
    )


class SynthesisConnectionDraft(BaseModel):
    note_labels: list[str] = Field(..., description="関係する2つ以上のノートのラベル（例: N1）")
    title: str = Field(..., description="関係を表す短い名詞句")
    explanation: str = Field(..., description="2つがどう関係するか（2〜3文）。ノートに書かれた内容だけで説明する")
    question: str = Field(..., description="この関係をユーザー自身に説明してもらう問い。答えを含めない")


class SynthesisContradictionDraft(BaseModel):
    note_labels: list[str] = Field(..., description="食い違っているノートのラベル")
    description: str = Field(..., description="どこがどう食い違っているか（1〜2文）")


class SynthesisDraftOutput(BaseModel):
    content: str = Field(..., description="テーマ全体のまとめ（Markdown）。段落ごとに根拠のラベルを [N1] の形で付ける")
    connections: list[SynthesisConnectionDraft] = Field(
        default_factory=list, description="ノートどうしの重要な関係。重要な順に最大5件"
    )
    contradictions: list[SynthesisContradictionDraft] = Field(default_factory=list)
    gaps: list[str] = Field(
        default_factory=list, description="テーマの理解に重要なのに、どのノートにも無い領域（短い名詞句、最大5件）"
    )
