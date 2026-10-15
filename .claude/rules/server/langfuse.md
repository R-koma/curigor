---
paths:
  - "server/observability/**"
  - "server/graph/llm.py"
  - "server/graph/nodes/**"
  - "server/main.py"
---

# Langfuse トレース

ルートの `CLAUDE.md` から分けた規約。一致するファイルを Read / Edit すると自動で読み込まれる。LLM 呼び出し・`run_name`・モデルの選択・`prompt_fingerprint`を触る前に関係すると分かっているときは先に読む。

- 送出は `observability/langfuse_tracing.py` に閉じている。クライアントは `main.py` の lifespan で `init_tracing()` / `shutdown_tracing()`（後者を省くと終了間際のトレースがバッチ送出されずに落ちる）
- 粒度は **1ターン＝1 trace・1対話セッション＝1 Langfuse session**。グラフは `interrupt_before` で毎ターン中断するため、実行の切れ目がそのままターンの境界になる
- グラフ実行は `traced_graph_run()` で自前の root span に包む。LangGraph の実行をそのまま root にすると trace の入出力が `LearningState` 丸ごと（かつ再開ターンでは入力 `None`）になり、一覧・評価器から読めないため。root span にはユーザー発話と応答だけを載せる
- `CallbackHandler` は root span が active な間に生成する必要がある（生成時点の trace context を引き継ぐため）。`build_graph_config()` が返す config に callbacks は入っておらず、`traced_graph_run()` が実行時に足す
- trace 名（`respond-to-user` 等）はダッシュボード・評価器の参照キーになるため、ID やターン番号を混ぜない。変更は破壊的変更として扱う
- `aget_state` / `aupdate_state` はノードを実行しないので callbacks を付けない（付けると中身のない trace が量産される）
- `pyproject.toml` の `langchain` は server のコードが import しない依存だが外せない。`langfuse.langchain` の `CallbackHandler` が `import langchain` で `__version__` を見て v0 / v1 の分岐をし、無いと `ModuleNotFoundError` になる。langfuse 自身は `langchain` を依存に宣言していない（#594）
- 環境変数: `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`（未設定なら送出は自動的に無効）・`LANGFUSE_BASE_URL`・`LANGFUSE_TRACING_ENVIRONMENT`（既定 `development`）
- **LLM 観測は Langfuse に一本化している**。ノードのレイテンシもトークン数も Langfuse 側にしか無いので、集計・eval のデータ源は Langfuse API を使う
- ノードが LLM を複数回呼ぶ場合（`generate_note` は最大5回（`generate-note-content`（→ まとめノートの候補 `suggest-collection`。出典が空で既存のまとめノートも無ければ呼ばない）・`estimate-category`・`analyze-dialogue`・`generate-aspect-map` を並行に走らせる）、`generate_feedback` は `generate_note` から分析を受け取れば `generate-feedback-scores` の1回、受け取れなければ（分析の失敗）3回（`analyze-dialogue` と `generate-aspect-map` を並行に走らせ、続けて `generate-feedback-scores`）、`update_note_and_feedback` は3回（`revise-note` と `append-review-addendum` は手での編集の有無でどちらか一方）、`learning_dialogue` は旧経路が dialogue intent 時のみ、地図駆動は毎ターン、事前分析分を含め2回、`review_dialogue` は事前分析（`review-turn-analysis`）と応答の2回（`confirmed` のターンは事前分析の1回）、`learning_start` は聞き取りカード生成の1回（`run_name` なし）、`explore_start` は `explore-turn-analysis` と応答の2回、`explore_dialogue` も同じく2回（`confirmed` のターンは事前分析の1回）、`generate_study_memo` は `extract-explore-terms` → `explore-teachback-map`（失敗時に `generate-depth-map`）と、並行に `summarize-explore-answers`（答えた疑問が無ければ呼ばない）、`finish_synthesis` は1回（`run_name` なし）、聞き取りのターンは常に完了ターンで、カード回答なら `generate-depth-map` を含め2回、自由文の返信なら `extract-intake` も含め3回（学習開始の声かけは事前分析を通さない））だけ `config={"run_name": "..."}` で呼び出しを識別する（`generate-note-content` / `estimate-category` / `generate-aspect-map` / `analyze-dialogue` / `turn-analysis` / `map-turn-analysis` / `extract-intake` / `generate-depth-map` など）。1ノード1呼び出しの対話ノードには付けない（ノードスパン名と二重になる）
- **モデルはタスクごとに `graph/llm.py` の `RESPONSE_MODELS`（応答の本文）と `STRUCTURED_MODELS`（構造化出力）で決める**: 呼び出し側は `llm.ainvoke(..., task=...)` / `llm_structured.with_structured_output(schema, task=...)` でタスクを渡す。タスク名は `run_name` があればそれと同じにし、`run_name` を付けない 1 ノード 1 呼び出しの対話ノードにも名前を持たせる（Langfuse ではノードスパン名で見分ける）。提供元は OpenAI と Anthropic で、Anthropic の現行モデルは `temperature` に既定以外の値を渡すと 400 になるので `ModelSpec.temperature` を `None` にする。クライアントは import 時に全タスクの分を作る（キーが無いと起動時に失敗する。テストにも CI と同じく偽の `OPENAI_API_KEY` が要る）。eval の report・capture の `model` / `temperature` は `learning-dialogue` の値
- **プロンプト本文の同一性は `prompt_version` ではなく `prompt_fingerprint`（質問生成 + 事前分析プロンプトの内容ハッシュ）で判定する**。`prompt_version` は手で維持するラベルなので、上げ忘れ・振り直しで本文との対応が崩れ、版ラベルで絞ると取りこぼす
- **`prompt_fingerprint` は経路ごとに別の値を持つ**。旧経路の質問生成は `PROMPT_FINGERPRINT`（`graph/prompts/question.py`）、地図駆動の応答生成は `MAP_PROMPT_FINGERPRINT`（`graph/prompts/map_question.py`。地図の事前分析を含む）、聞き取りカード・抽出・学習開始の声かけ・深さの地図生成は `INTAKE_PROMPT_FINGERPRINT`（`graph/prompts/intake.py`）、つながりの対話と下書きは `SYNTHESIS_PROMPT_FINGERPRINT`、インプットセッションの事前分析・応答・用語・回答要約・学習メモの地図は `EXPLORE_PROMPT_FINGERPRINT`（`graph/prompts/explore.py`。失敗時の通常の地図の生成は `INTAKE_PROMPT_FINGERPRINT` のまま）。metadata のキーはどれも `prompt_fingerprint` なので、値で経路を見分ける。地図駆動のプロンプトは旧経路の本文・応答例を流用しているため、旧経路のプロンプトを直すと `MAP_PROMPT_FINGERPRINT` も動く（逆は動かない）。深さの地図は state に保存されるので、ターンの再現に効くのは `MAP_PROMPT_FINGERPRINT` だけ
- **`config={"metadata": ...}` を渡しても trace 属性（session / user / tags）は落ちない**が、それは冗長性に支えられている。`ensure_config` は contextvar 側の metadata を**マージせず置換**するため、`build_graph_config()` が入れている `langfuse_*` キーはその observation から消える。それでも属性が付くのは `traced_graph_run()` が `propagate_attributes()` で OTEL レベルにも同じ属性を伝播しているため（切り分け実験で両経路が独立に機能することを確認済み）。**`traced_graph_run` の外でグラフや LLM を実行しつつ metadata を上書きすると、session グルーピングが静かに壊れる**
- 文字起こしの用語の一覧（`services/transcription_keywords.py`）は WS の応答の後にバックグラウンドで作るのでグラフの外にあり、`traced_transcription_keywords()` が `generate-transcription-keywords` の span で包み、対話セッションの session と user に紐づける。プロンプトの同一性は `TRANSCRIPTION_KEYWORDS_PROMPT_FINGERPRINT`
- まとめの下書きの生成（`POST /api/collections/{id}/synthesis`）はグラフの外なので、`traced_synthesis()` が `generate-collection-synthesis` の span で包み、`CallbackHandler` で LLM 呼び出しを記録する。session は持たず user と `synthesis` タグだけを付ける。プロンプトの同一性は `SYNTHESIS_PROMPT_FINGERPRINT`（`graph/prompts/synthesis.py`）
