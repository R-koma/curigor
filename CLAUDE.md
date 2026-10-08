# CLAUDE.md

## プロジェクト概要

「プロテジェ効果」（教えることで学ぶ）を活用した AI 学習アプリ。ユーザーが LLM と対話しながら学習し、ノート・フィードバック・復習スケジュールが自動生成される。

- **client/**: Next.js 16 (App Router) + React 19 + TypeScript（Node.js 24。`client/.nvmrc` と `engines` で固定し、CI・Dockerfile も同じ）
- **server/**: Python 3.13 + FastAPI + LangGraph
- **DB**: PostgreSQL 17 + pgvector（asyncpg で非同期アクセス、ORM 不使用。イメージは `pgvector/pgvector:pg17`）
- **認証**: BetterAuth（client）→ JWT + JWKS（server で EdDSA 検証）
- **リアルタイム**: WebSocket `ws://localhost:8000/ws/chat`

---

## 開発コマンド

### バックエンド（`server/`）
```bash
uv run fastapi dev main.py                                    # 開発サーバー
uv run alembic upgrade head                                   # マイグレーション適用
uv run alembic revision --autogenerate -m "description"       # マイグレーション生成
uv run ruff check . --fix && uv run ruff format .             # Lint + フォーマット
uv run mypy .                                                 # 型チェック（strict）
uv run pytest                                                 # テスト全実行
uv run pytest --cov=. --cov-report=term                      # カバレッジ付き

uv run python -m evals.eval --mode scoring                    # 保存済み出力を採点（judge–人間一致を出す。既定は Haiku→Opus カスケード）
uv run python -m evals.eval --mode regression --runs 5        # input から再生成して採点（現行プロンプトの測定）
uv run python -m evals.eval --mode scoring --no-cascade        # カスケードを無効化し screen 単体で判定（従来の単一 judge）
uv run python -m evals.eval --mode scoring --strict            # 校正ゲート（TPR/TNR≥90%・正例レコード全件pass）不合格で exit 1
uv run python -m evals.eval --emit-instance <trace_id>        # golden の写しを正本 jsonl から生成
uv run python -m evals.eval --list-unannotated                 # 人間ラベル（pass）が無いレコードを一覧
uv run python -m evals.eval --mode regression --replay-mode pinned  # 保存済みの turn_decision を注入して応答生成だけ再実行
uv run python -m evals.eval --mode regression --route map --runs 3  # 経路で絞る（map / legacy / all。既定 all。校正ゲートは all で見る）
uv run python -m evals.eval --mode regression --emit-jsonl <path>  # regression の生成を正本へ追記
uv run python -m evals.eval --checkpoint-dir evals/reports/<name>  # 生成・採点の保存先を固定し、再開できるようにする（既定は自動生成）
uv run python -m evals.eval --mode scoring --no-judge-cache    # 保存済みの judge の判定を読まずに採点する（判定の揺れを見るとき）
uv run python -m evals.eval --mode regression --route map --trace <id> --no-cascade  # 指定した instance だけを安く確かめる（途中の確認用。--strict とは併用不可）

uv run python -m evals.tools.capture --list                   # 直近の learning セッション一覧
uv run python -m evals.tools.capture --latest --dry-run       # 直近セッションの生成レコードを表示（追記しない）
uv run python -m evals.tools.capture --session-id <uuid>      # 指定セッションを正本 jsonl へ追記（id 重複はスキップ）

uv run python -m evals.tools.annotate                         # annotate と golden 昇格の UI（http://127.0.0.1:8100）
```

> **Note:** jsonl の `input.graph_state` は**生成直前**の state（再実行の入力）で、`turn_decision` は
> **そのターンがプロンプトへ注入した値**（`response_mode` / `selected_aspect` / `error_summary` /
> merge 後の `covered_aspects`。`output` の直後・`input` の外）。`turn_analysis` はノードが読まずに
> 書くだけの値なので `input.graph_state.turn_analysis` は「前のターンの決定」であり、決定を注入して
> 再生成する用途（`--replay-mode pinned`）に使ってはいけない。
>
> **Note:** `input.graph_state.wrap_up_offered` が**無い**レコードは区切りの提案（`wrap_up`）を導入する前の
> capture であり、regression では提案済み扱いにして従来の質問応答を再生する（導入前に 23 件中 7 件が既に
> 完了基準を満たしていたため、そのままだと区切り応答に化け、質問応答を前提とした golden が壊れる）。
> 区切り応答の golden は導入後に capture したレコードで別途作ること。
>
> **Note:** regression は **capture 由来のレコード（`meta.captured_by`）だけを再生成する**。手で転記した
> レコードは `conversation_history` が本番の `messages` と 1:1 になっておらず（トピック発話や
> `learning_start` の応答が欠けている）、`classify_user_intent` の判定とプロンプトの直近履歴が本番と
> 変わるため。スキップした理由は report に出る。`meta.route: "map"`（地図に沿った経路）のレコードも再生できる。
>
> `--route map|legacy|all`（既定 `all`）で経路を選び、ベースラインは経路ごとに取る（地図は `evals/baselines/map-v3-full.json`。v3 は地図の golden を 12 件に増やした後の記録で、v2 以前とは対象の件数が違うので数値を比べない。v1 は #375 前の旧プロンプトの記録）。`map-v3-full.json` は #449 で地図経路の案内文を「下のボタン」へ直す前（`MAP_PROMPT_FINGERPRINT` が動く前）の記録で、取り直すまで地図の数値を比べない。
> checkpoint の実行条件は `route` と `map_prompt_fingerprint` も含むので、地図側のプロンプトを直すと既存の checkpoint では再開できない。
> レポート `meta.prompt_fingerprint` は旧経路の値のままなので、地図のベースラインどうしは `meta.map_prompt_fingerprint` で比べる。
>
> **Note:** トピック訂正の確認を出したターン（`turn_analysis.topic_correction.status == "asked"`）は LLM が応答を生成しないので capture の対象外。回答のターン（`accepted` / `declined` / `failed`）は `pinned` では再生できるが、回答の印を `conversation_history` が持たないため `full` では再生できない（`replay_blocker` が理由を出す）。
>
> **Note:** judge の判定は `evals/.judge_cache/`（gitignore）に、送った内容（モデル・判定の形式・プロンプト本文。基準・入力・応答を含む）の
> ハッシュで保存し、次の実行で同じ内容なら API を呼ばずに使う（`evals/judge_cache.py`）。基準を 1 つ直したときは、その基準の判定だけが
> 採点し直しになる。保存した判定を使うので、同じ入力に対する判定の揺れは現れない。揺れを見るとき・judge のモデルの中身が変わったときは
> `--no-judge-cache` で採点し直す。
>
> **Note:** jsonl の `source` と `failure_mode` / `first_failure` の値空間は `evals/taxonomy.py` が正本。
> 追加は `tests/unit/evals/test_dataset_invariants.py` が強制する（自由文字列だと表記ゆれで集計が割れる）。
>
> **Note:** capture は**セッション直後に実行する**。`meta`（model / prompt_version / prompt_fingerprint）は
> 実行時点のコードの値であり、セッション実施時点の値ではない。遡及エクスポートでずれた場合の一次資料は
> Langfuse の該当 trace（`sessionId = dialogue_session_id`）だが、Hobby プランは 30 日でデータアクセスが切れる。
>
> **Note:** eval は生成・採点を `--checkpoint-dir`（既定は `evals/reports/` 配下に自動生成）へ常に保存する。
> 途中で切れても、同じディレクトリを指定して再実行すれば保存済みの run は作り直さない。実行条件
> （プロンプト・judge・golden/rubric 本文などのハッシュ）が前回と違うディレクトリでは拒否される。
> 接続断・レート制限は自動で再試行するが、課金枯渇（クレジット・quota 切れ）は再試行しても直らないため
> 実行全体をその場で止める。保存済みの分はそのまま再開に使える。

### フロントエンド（`client/`）
```bash
npm run dev              # 開発サーバー
npm run build            # ビルド
npm run lint             # ESLint
npx tsc --noEmit         # 型チェック
npm run test             # Vitest（一回実行）
npm run test:watch       # ウォッチモード
```

### その他
```bash
make adr name=your-title  # docs/adr/ にアーキテクチャ決定記録を生成
make test-db              # テスト用 DB 起動
```

---

## ディレクトリ構成

```text
server/
├── main.py                    # FastAPI エントリーポイント・lifespan
├── api/
│   ├── routes/                # REST エンドポイント（note, feedback, review_schedule, dialogue_session）
│   ├── websocket/chat.py      # WebSocket ハンドラ
│   └── dependencies.py        # CurrentUser, DB (Depends 注入)
├── core/
│   ├── auth.py                # JWT / JWKS 検証
│   ├── config.py              # 環境変数
│   └── database.py            # asyncpg コネクションプール
├── graph/                     # LangGraph ワークフロー
│   ├── builder.py             # グラフ定義・route_entry と経路ごとの route_after_*_dialogue
│   ├── state.py               # LearningState TypedDict
│   ├── nodes/                 # learning_start, learning_dialogue, generate_note, generate_feedback, review_start, review_dialogue, update_note_and_feedback, synthesis
│   └── prompts/               # タスク別プロンプト（intake, depth_map, map_question, analysis, note, feedback, review, question）
├── observability/             # langfuse_tracing.py（Langfuse へのトレース送出）
├── repositories/              # SQL-first データアクセス（asyncpg 直接）
├── schemas/                   # Pydantic モデル（リクエスト/レスポンス）
├── storage/                   # 対話添付のオブジェクトストレージ抽象（local 実装、S3 は #128 で追加）
├── embedding/                 # 埋め込みの抽象（OpenAI 実装）
├── scripts/                   # 単発の運用スクリプト（backfill_note_embeddings など）
├── transcription/             # 音声の文字起こしの抽象（OpenAI gpt-transcribe 実装）
├── speech/                    # 応答の読み上げの抽象（OpenAI gpt-4o-mini-tts。PCM のストリーミング）
├── services/review_scheduler.py
├── migrations/                # Alembic（env.py, versions/）
├── evals/                     # eval.py（scoring / regression）・checks.py・golden_yaml.py・taxonomy.py・tools/capture.py + datasets/ + README.md（golden の規約・judge の決定）
└── tests/
    ├── unit/                  # pytest + 実 DB（モック禁止）
    └── integration/

client/
├── app/
│   ├── (auth)/                # sign-in, sign-up
│   ├── (main)/                # dashboard, learn, notes/[id], review/[noteId]
│   └── api/                   # Next.js Route Handlers（auth/[...all], upload-avatar）
├── context/                   # navbar-slot-context.tsx（ナビバー差し込み）
├── components/
│   ├── chat/                  # chat-input など
│   ├── layout/                # sidebar, navbar, main-layout-client
│   ├── notes/
│   └── ui/                   # shadcn/ui コンポーネント
├── hooks/use-chat-websocket.ts # WebSocket ライフサイクル管理
├── lib/
│   ├── api.ts                 # fetchAPI()（JWT 自動付与）
│   ├── auth.ts / auth-client.ts
│   ├── auth-otp.ts / auth-hooks.ts  # email-otp の設定・新規ユーザーの名前
│   ├── dev-auth.ts            # 開発用の固定コード・自動ログインの判定（server-only）
│   ├── email/                 # OTP のメールの組み立てと Resend での送信
│   └── utils.ts
└── __tests__/                 # Vitest テスト
```

---

## アーキテクチャ詳細

### LangGraph ワークフロー

```
route_entry（session_type で入口を分ける）
  ├─ "learning"  → learning_start  → learning_dialogue（ループ） → generate_note → generate_feedback → END
  ├─ "review"    → review_start    → review_dialogue（ループ）   → update_note_and_feedback → END
  └─ "synthesis" → synthesis_start → synthesis_dialogue（ループ）→ finish_synthesis → END
```

- 入口の分岐は `graph/builder.py` の `route_entry`、ループを抜けるかは経路ごとの `route_after_learning_dialogue` / `route_after_review_dialogue` / `route_after_synthesis_dialogue` が `should_generate_note` で決める
- 復習セッション: `review_start` / `review_dialogue` が既存ノートの本文・要約と前回の改善点（`prior_improvements`）をプロンプト（`graph/prompts/review.py`）に注入し、`update_note_and_feedback` でノート・フィードバック・復習スケジュールを更新する（`generate_note` / `generate_feedback` は通らない）。`review_dialogue` は毎ターン事前分析（`ReviewTurnAnalysis.wants_to_end_session`）で終える意志を判定する。`should_generate_note` は立てない（終了は下の「会話でのセッション終了」）
- **synthesis セッションは、いま何番目のつながりを聞いているかを state に持たず、`messages` のユーザー発言の数から決める**（`graph/nodes/synthesis.py` の `current_connection_index`）。発言の取り消しと応答の無い発言の巻き戻しは `messages` だけを巻き戻すので、位置を別の値で持つとずれる。synthesis セッションは再開しない（`find_resumable_by_user` の対象外）
- `interrupt_before=["learning_dialogue", "review_dialogue", "synthesis_dialogue"]` でユーザー入力待ちのため毎ターン中断する（再開はチェックポイントから）
- ノードスパン・LLM 生成の計測は Langfuse が自動で行う（`observability/langfuse_tracing.py`）。詳細は「Langfuse トレース」節
- グラフ状態は `langgraph-checkpoint-postgres` で DB に永続化
- `LearningState` は `session_type`（`"learning"` / `"review"` / `"synthesis"`）で分岐
- **プロンプトを変える決定値は state に残す**。`learning_dialogue` の事前分析が決める `response_mode` / `selected_aspect`（`turn_analysis`）は、無いと会話履歴と state からターンを再現できず eval の regression が成立しない。同じ理由で、新しく「プロンプトに注入するがどこにも保存しない値」を作らないこと
- **区切りの提案（`wrap_up`）は LLM ではなく `covered_aspects` から決定的に決める**（`graph/coverage.py` の `coverage_progress`）。exemplified 以上の観点が `WRAP_UP_MIN_ASPECTS` 個（`focus_aspects` 指定時はその全観点）に届き、誤りが無く、未提案（`wrap_up_offered`）のターンだけ質問をやめて区切りを提案する。提案は 1 セッション 1 回で、終了はさせない。`focus_aspects` は判定上 `covered_aspects` と**表記の完全一致**で照合するため、事前分析が表記を揺らすと完了しない。なお `cancel_last_message` は `covered_aspects` / `wrap_up_offered` を巻き戻さない
- **毎ターン置き換わる state フィールドは、値が無いターンにも明示的に `None` を書く**。LangGraph はキーを省いた更新では前ターンの値を保持するため、書かないとチェックポイント履歴を辿る側（eval エクスポート）が別ターンの値を読む。累積する `covered_aspects` と、置き換わる `turn_analysis` の違いに注意
- state フィールドの追加は `NotRequired` にし、読む側は `.get()` で欠損許容する（旧チェックポイントにキーが無い）。トポロジーが変わらないなら `GRAPH_VERSION` は上げない（上げると進行中セッションが全て再開不可になる。ただしフィールドの削除・改名は例外 — 「注意事項」節参照）
- **`learning_dialogue` は `intake_complete` キーの「有無」で3経路に振り分けるルーター**: キー欠損 = デプロイ前に始まった旧セッション（旧経路 `prepare_turn`/`respond` をそのまま実行）、`False` = 聞き取り中（`graph/nodes/_intake.py`）、`True` + `depth_map` あり = 地図駆動（`_map_dialogue.py`）、`True` + `depth_map` なし = 地図生成に失敗した旧経路フォールバック。値ではなく**有無**で旧セッションを見分けるため、`learning_start` は新規セッションで必ず `intake_complete=False` を書く（省くと新規セッションが旧経路へ落ちる）。`evals/eval.py` の regression が旧 capture を再生できるのも、`to_state` がこのキーを持たないから。聞き取り中（`intake_complete=False`）は進捗（`LearningProgress`）を送らない（地図が無く、旧経路のフォールバックが意味のない 0/3 を返すため）。聞き取りの完了ターンで地図生成が失敗すると `handle_intake_turn` は `messages` キーを含まない dict を返し、ルーターが旧経路で応答を作る（`_intake.py` から `learning_dialogue.py` を import すると循環になるため）。`evals/tools/capture.py` は `intake_complete` を持つセッションを `meta.route: "map"` のレコードとして capture する（対象は order 6 以降の、直前の state に `depth_map` があるターンだけ。声かけと、地図生成に失敗して旧経路で応答したターンは対象外）。regression は地図のレコードを、`to_state` が `intake_complete=True` と生成直前の地図（`depth_map` / `map_covered` / `intake_message_count`）を入れて地図の経路で再生する（`pinned` は `turn_decision` から `MapTurnPlan` を組んで `respond_map` を直接呼ぶ）。`route` を持たない旧 capture には `intake_complete` を入れない
- **地図駆動の経路は、発言の種類（`user_intent`）を事前分析が毎ターン判定する**（`MapDialogueTurnAnalysis.user_intent`）。値は `explanation` / `dont_know` / `partial_dont_know` / `question` / `exhausted` / `end_session` で、応答のプロンプトはこれで分岐する（`map_question.py` の `_build_intent_section`）。キーワード判定（`classify_user_intent`）は、事前分析が失敗したときと、`user_intent` を持たない旧 capture の再生にだけ使う。「わからない」の連続回数 `unknown_streak` は LLM に決めさせず、直前の `turn_analysis`（`user_intent` と `unknown_streak`）から数える。直前の `turn_analysis` が空（意図の判定を入れる前の地図の経路が「わからない」のターンに残した値。旧 capture と、デプロイ前に始まったセッション）なら、それまでのユーザー発言をキーワード判定で遡って数える。`turn_analysis` には、既定値（`explanation`・0）のときはこの 2 つのキーを書かない（旧 capture の `turn_decision` と形をそろえ、pinned の再生で決定が一致するようにするため）。読む側は `.get` で既定値を補う。`end_session` の応答は問いを出さず、画面の「ノートを作成」へ案内するだけで、セッションは終えない（会話での終了は #449 がこの判定の上に作る）。Langfuse の metadata の `intent` は、地図駆動では `user_intent` の値になる
- **`learning_start` は最初の発言から正規化したトピックと聞き取りカードを返す**: 発言は `state["topic"]` に入って `start_learning.topic` として届き、`learning_start` が短いトピック名へ正規化して `topic` を上書きする（`dialogue_sessions.topic` にも保存。NULL なら最初のユーザー発言）。カードは AIMessage の `additional_kwargs["intake_card"]`、回答は HumanMessage の `additional_kwargs["intake_answers"]` に載る。カードの回答は `dialogue_messages.intake_answers` にも保存し、画面はこれを印に吹き出しの代わりに 1 行の表示を出す（カード直後の自由文と再開時に見分けるため。`content` は LLM が読むので整形済みの本文のまま変えない）。ストリームは流れないので WS は `intake_question` で送り、`dialogue_messages.intake_card` に保存して再開時に復元する。聞き取りは1往復で必ず完了し、カードを無視した自由文の返信は従来どおり `extract_intake` で抽出する
- **最初の発言が曖昧なら、聞き取りカードの先頭に `topic` の質問を足す**: `IntakeCardDraft.topic_is_clear` が false（指示語だけ・対象が書かれていない）のとき、`build_intake_card` が候補（0〜3 件。手がかりが無ければ 0 件で、既定の選択肢は作らない）付きの質問を先頭に入れる。確かめたかどうかは state に持たず、カードの AIMessage に topic の質問があるかで決まる（`_intake.py` の `_topic_was_asked`）。それまでの `state["topic"]` は発言から作った仮の値で、聞き取りの完了ターンが回答（カードは `intake_answers.topic`、自由文は聞いたときだけ `extract_intake` が抽出する `topic`）で上書きしてから、深さの地図と声かけを作る。スキップされたら仮の値のまま。draft の生成に失敗したときは確かめない。`dialogue_sessions.topic` とナビバーは、各セッションが毎ターン `assistant_message_end.topic` で運ぶ値（学習は state のトピック、復習はノートのトピック、synthesis はまとめノート名）を `SessionContext.topic` と比べ、変わったときだけ更新する（聞き取りに限らない）。上限 60 字は `MAX_TOPIC_LENGTH`・`IntakeAnswers.topic`・クライアントの `TOPIC_MAX_LENGTH` で一致させる
- **地図駆動の対話の途中でトピックの訂正を受け付けるが、適用の前に必ず確認する**: 地図の事前分析（`MapDialogueTurnAnalysis.corrected_topic`）が訂正を判定すると、そのターンは適用せず、LLM を使わない確認文（`graph/topic_correction.py`）を AIMessage（`additional_kwargs["topic_correction_card"]`）で返し、`pending_topic_correction` を残す。ストリームは流れないので WS は `topic_correction_question` で送り、`dialogue_messages.topic_correction_card` に保存して再開時に復元する。回答は聞き取りカードと同じく通常の `user_message` に `topic_correction_answer`（`accept` / `decline`）を付けて送り、`dialogue_messages.topic_correction_answer` にも保存する。保留があり最後の発言に回答の印があるときだけ、事前分析と意図の判定を飛ばして決定的に分岐する。`accept` は聞き取りと同じ `generate_depth_map`（`graph/nodes/_depth_map_generation.py`）で地図を作り直し、学習の前提は引き継ぎ、`map_covered` を空に・`wrap_up_offered` を `False` に戻す（観点 id は地図ごとに振られ、旧トピックの到達度は対応しない）。訂正の発言の `observations` は捨てる。作り直しに失敗したら `topic` も地図も変えない（`failed`）。保留があるのに自由文を送ったら `decline` 扱いで保留を捨てる。今のトピックと（NFKC・大小無視で）同じなら訂正として扱わない。`pending_topic_correction` は毎ターン置き換わるので、`respond_map` は値が無いターンにも `None` を書く。判定は `turn_analysis.topic_correction`（`previous_topic` / `new_topic` / `status`: `asked` / `accepted` / `declined` / `failed`）に残る。`asked` のターンは LLM を呼ばないので、`turn_analysis` の `response_mode` などは空の値で埋めた名目の値で、プロンプトには注入されていない（`topic_correction.status` で見分ける）。`dialogue_sessions.topic` とナビバーは `assistant_message_end.topic` の既存経路で更新される。旧経路は対象外。回答の発言は取り消せない（`_handle_cancel_last_message` が拒否し、`_rollback_unanswered_turn` は聞き取りカードと同じく本文を空で返す）。確認を出したターンの取り消しは許し、`pending_topic_correction` も `None` に戻す
- **ヘッダーのトピック名からも編集できる**（`NavbarTopic` の `onEdit`）: クライアントの `AlertDialog` で確認済みなので、サーバーは確認を挟まずに適用する。`user_message.topic_edit` を付けた発言（本文は `topic_edit_text`。`dialogue_messages.topic_edit` にも保存）を 1 ターン流し、`prepare_map_turn` が事前分析を飛ばして会話での訂正の確定と同じ `generate_depth_map` で作り直す（保留中の `pending_topic_correction` は捨てる）。記録は `topic_correction` に `source: "header"` を足して残し（会話での訂正は `source` を書かない。読む側は `.get`）、応答のプロンプトは `accepted` / `failed` の節をそのまま使うので `MAP_PROMPT_FINGERPRINT` は動かない。WS は学習以外のセッション・聞き取りの途中・地図が無い・同じトピックでは発言ごと拒否して `topic_edit_rejected` を返す（DB にも state にも入れない）。この発言は取り消せず（`_handle_cancel_last_message` が拒否）、巻き戻しは本文を空で返す。eval の `full` 再生はトピック訂正への回答と同じく止まる
- **関連する過去のノート（`related_notes`）は聞き取りの完了ターンで 1 回だけ取り、以後は変えない**: `handle_intake_turn` が確定したトピックと学習目的を埋め込み（`services/related_notes.py`。Langfuse は `embed-related-notes-query`）、同じユーザーのノートを近い順に `RELATED_NOTES_LIMIT` 件まで（`RELATED_NOTES_MIN_SIMILARITY` 以上）state に書く。該当が無いとき・埋め込みや検索に失敗したとき（`RELATED_NOTES_TIMEOUT_SECONDS` で打ち切る）も空リストを書く。深さの地図の生成（前提知識と同じ扱い）と地図駆動の応答（`map_question.py` の「過去に学んだノート」の節。未出の概念の規則の例外はこの節に書き、ノートが無いときのプロンプトは変えない）に注入する。トピックの訂正で地図を作り直すときも取り直さず同じ値を渡す。キーが無い state（この機能より前のセッション・旧 capture）は注入しない。capture は state にキーがあるときだけ `input.graph_state.related_notes` に入れ、regression はそれを再生する（既存の golden では効果を測れない）
- **`should_generate_note` は学習・復習の全対話ノード（`respond` / `respond_map` / 聞き取りの `base_updates` / `review_dialogue`）で常に `False` を返す**: セッションはユーザーの明示的な終了操作で完了し、終了スイッチは `api/websocket/chat.py` の `_handle_end_session` が外部から立てる。対話ノードから立てると、確認を挟む前に終わってしまう
- **会話でのセッション終了は確認を挟む**（#449）: 地図経路は `user_intent == "end_session"`、復習は `wants_to_end_session` で終える意志を判定し、ノードは `end_confirmation`（`offered` / `confirmed` / `None`。毎ターン置き換わるので値が無いターンも `None` を書く）を書く。区切りの提案（`wrap_up`）のターンも `offered`。`offered` の次のターンで再び終える意志が判定されると `confirmed` になり、ノードは LLM を呼ばず応答も足さない（アシスタントの行も保存されないので capture の対象にならない）。WS の `_handle_user_message` が `confirmed` を見て終了ボタンと同じ `_handle_end_session` を呼び、メインのループは終了後に抜ける（`end_session` と同じ）。旧経路は会話での終了を判定しない。取り消し（`_handle_cancel_last_message`）は `end_confirmation` を `None` に戻す。確認ボタンは `assistant_message_end.end_confirmation` / `session_resumed.end_confirmation`（`creates_note`）で送り、`_stream_ai_response` は学習・復習とも state を読んで載せる。表示の状態は保存せず、再開時に state から復元する
- **ノートを作るかは `graph/session_end.py` の `has_learner_content` だけで決める**: ボタン・会話・声のどれで終えても `_handle_end_session` が state を読んでこれを見て、偽ならノート・フィードバック・復習予定を作らず `status = 'completed'`（`note_id` は NULL）で終え、`session_ended.note_skipped` を送る。復習は `review_answered`（終える意志だけの発言は数えない）で判定し、このキーが無い（導入前に始まった）セッションは、`review_start` がトピックを最初の HumanMessage として入れるので、それを除いた HumanMessage の数で数える

### API エンドポイント

| Method | Path | 用途 |
|--------|------|------|
| GET | `/api/health` | ヘルスチェック |
| GET/PATCH | `/api/notes` | ノート取得・更新 |
| GET | `/api/feedbacks` | フィードバック取得 |
| GET | `/api/review-schedules` | 復習スケジュール |
| GET | `/api/dialogue-sessions` | セッション一覧 |
| GET/POST/PATCH/DELETE | `/api/collections` | まとめノート（ノートの束ね先） |
| PUT/DELETE | `/api/notes/{id}/collection`, `/collection-suggestion` | ノートをまとめノートに入れる・外す・候補を断る |
| GET/PUT | `/api/notes/{id}/links`, `/links/{link_id}` | 別のまとめノートのノートとのつながり（候補・採用済み）の取得と採否 |
| GET/POST | `/api/collections/{id}/synthesis` | まとめの下書きの取得・生成（同期） |
| POST | `/api/transcriptions` | 音声の文字起こし（multipart。`audio/wav` の発話区間を含む） |
| POST | `/api/speech` | 応答の読み上げ（JSON → PCM のストリーム） |
| WS | `/ws/chat` | チャット WebSocket |

### データアクセスパターン

- リポジトリパターン（`repositories/`）: SQL を直接記述、asyncpg で実行
- 依存性注入: `CurrentUser`（JWT 検証済みユーザー ID）と `DB`（コネクション）を `Depends()` で注入
- ORM 不使用、`asyncpg.Record` を直接扱う
- リポジトリ関数の接続引数は `core.database.DBConnection`（`Connection | PoolConnectionProxy`）を使う。`pool.acquire()` が返すのは `Connection` の非サブクラスである `PoolConnectionProxy` のため、両方を受け取れる必要がある（`Pool` を直接渡さず、必ず `acquire()` してから渡す）

### 認証（メール OTP）

- 方式の決定は `docs/adr/013-email-otp-auth.md`。パスワード認証は無い。新規登録とログインは同じフォームを `/sign-in` と `/sign-up` の 2 つの入口から出し（文言と相互リンクだけが違い、動作は同じ。登録済みかどうかは画面で区別しない）、better-auth の `email-otp`（設定は `lib/auth-otp.ts`）と Google を使う。FastAPI の JWT 検証は認証方式に依存しない
- メールの送信は `lib/email/send-email.ts` の `sendEmail()` だけが Resend に依存する。`RESEND_API_KEY` が無い開発環境では、コードをコンソールに出す。本番ではコードをログに出さない
- 開発環境専用の固定コードと自動ログインがある。判定は `lib/dev-auth.ts` だけが持ち（`server-only`）、詳細はそのファイルを読むこと。**効くのは `@example.test` のアドレスだけ**で、これは設定が本番に漏れても本物のユーザーのアカウントに届かないようにするための守りの本体。この制限を緩めないこと
- 本番（`NODE_ENV=production`）で開発用の変数が空でない値だと、`lib/dev-auth.ts` の読み込みが例外になる。`next build` も `NODE_ENV=production` で動くため、開発用の変数が設定されているとビルドも失敗する
- 開発用の変数に `NEXT_PUBLIC_` を付けない。ログイン画面には `lib/dev-auth.ts` で判定した真偽値だけを Server Component から渡す（`__tests__/lint/server-only-boundary.test.ts` が検査する。CI は `next build` を実行しないので `server-only` の検査は CI で効かない）
- OTP メールのロゴは `cid:` のインライン画像で付ける（HTML に外部 URL を入れない。`otp-email.test.ts` が検査する）。メールクライアントは SVG を表示しないので、PNG を `lib/email/logo-png.ts` に base64 で持つ。`app/icon.svg` を直したら、viewBox を `1.5 7.25 29.75 17.5` にして幅 240px で PNG にし直して差し替えること（`sharp` で作れる）
- 新規ユーザーの名前は、`lib/auth-hooks.ts` の `databaseHooks` がメールアドレスの `@` より前で埋める（`email-otp` は名前を空文字で作るため）
- 開発サーバーは `127.0.0.1` にだけ公開する（`docker-compose.yml`。worktree で `npm run dev -- -p 3001` を使うときも `-H 127.0.0.1` を付ける）。開発用の自動ログインが同じ LAN から届かないようにするため
- 環境変数: `RESEND_API_KEY`・`EMAIL_FROM`（開発用の変数は `lib/dev-auth.ts` を参照）

### 画像添付（マルチモーダル）

- 対話の `user_message` に画像（JPEG/PNG/WebP・最大4枚・各5MB）を添付できる。クライアントは送信前に長辺2048pxへ縮小し base64 で送る（`client/lib/image.ts`）
- バイナリは `storage/`（dev: ローカルFS、本番: S3 は #128）に保存し、参照メタは `dialogue_message_images` テーブルに持つ。state（チェックポイント）には base64 を載せず storage_key 参照のみ保持し、LLM 呼び出し直前にストレージから読んで base64 data URL を組む（`graph/multimodal.py`）
- LLM へは最新ユーザーメッセージの画像のみ `image_url`（detail=high）ブロックで渡す（会話履歴はプロンプト本文に文字列化されるため）。ノート/フィードバック生成には画像を渡さない
- 履歴の画像は `GET /api/dialogue-sessions/{id}/images/{image_id}` で配信（Bearer 認証必須のためフロントは `fetchImageObjectURL()` で取得）
- 環境変数: `STORAGE_BACKEND`（既定 `local`）・`LOCAL_STORAGE_DIR`（既定 `storage_data`）
- 動画は対象外（音声は次節「音声入力（STT）」）

### 音声入力（STT）

- 方式の決定は `docs/adr/007-voice-input-stt.md`。録音（push-to-talk）を `POST /api/transcriptions`（multipart: `audio`・任意の `dialogue_session_id`・任意の `prompt`。`prompt` は `MAX_TRANSCRIPTION_PROMPT_CHARS` 文字まで）で文字起こしし、結果を入力欄に入れてユーザーが確認・修正してから、通常の `user_message` として送る。グラフ・state・eval・capture は音声を知らない
- 新規学習の最初の画面（トピック入力）でも使える。この時点ではセッションが無いので `dialogue_session_id` を省き、使用量は `dialogue_session_id = NULL` で記録し、Langfuse の trace は user だけに紐づく。最初の発言の修正前の文字起こしは `start_learning` の `raw_transcript` で送り、最初の `dialogue_messages` 行に保存する。マイクを出すかは `ChatInput` の `allowVoice` で決める（`sessionId` の有無ではない）。聞き取りカードは選択肢を声で選ばせず、問いを読み上げて自由に話した回答を入力欄で確認して送る（音声対話節）
- 音声は保存しない。修正前の文字起こしは送信時に `raw_transcript` として送り、`dialogue_messages.raw_transcript` / `input_mode`（`text` / `voice` / `voice_auto`）に残す。プロンプトに注入しない値なので `HumanMessage` にも state にも載せない
- 1回 300 秒（クライアントで自動停止・64kbps 固定）、受付 5 MiB、`audio/webm` / `audio/mp4` / `audio/wav`（44 バイトの標準ヘッダー・PCM 16bit モノラルのみ。「声で話す」の発話区間）。ブラウザは `audio/webm;codecs=opus` のようにパラメータ付きで送るので、MIME はパラメータを落として比較する
- 1日の上限は音声の秒数（`DAILY_TRANSCRIPTION_SECONDS`）。WAV の長さは実際のバイト数から計算し（ヘッダーのサイズ欄は信用しない）、webm / mp4 は録音が 64kbps 固定なので `audio_bytes / 8000` 秒とみなす（低ビットレートに偽装したアップロードは過小に数えうる。1 回 5 MiB の上限が頭打ちにする）。成功した文字起こしだけを `transcription_usages`（`audio_seconds`）に記録し、`REVIEW_TIMEZONE` の暦日で数える。上限の判定はアトミックではない（同時リクエストで超えうる）
- 文字起こしはグラフの外なので、Langfuse には `traced_transcription()` が `transcribe-audio`（generation）として、対話セッションの session に紐づけて送る
- 環境変数: `TRANSCRIPTION_MODEL`（既定 `gpt-transcribe`）。認証は既存の `OPENAI_API_KEY`。OpenAI クライアントは 120 秒・再試行 1 回に絞っている

### 音声対話（声で話す）

- 方式の決定は `docs/adr/010-voice-conversation.md`（ADR-008 の音声モードを置き換えた）。学習と復習のチャット画面の入力欄の「声で話す」で始まり、入力欄の場所が `VoicePanel` に置き換わる。速度は端末ごとに `localStorage`（`voice-speed`）へ保存する。グラフ・state・eval・capture は音声を知らない
- 入力は `lib/mic-capture.ts`（`AudioWorklet`（`public/worklets/pcm-capture.js`）で 16kHz・20ms のフレーム）→ `lib/vad.ts`（音量の VAD）→ `lib/stt/`（`LiveTranscriber`。第 1 段階は区間ごとに WAV で `POST /api/transcriptions` する `segmented`）。状態遷移・割り込み・送信は `useVoiceConversation` に閉じる
- `openMicCapture` は準備に失敗したらどの段階でもマイクを手放し、suspended の `AudioContext` は `resume()` する。`useVoiceConversation.start` は `startingRef` と開始ごとのトークンで二重開始を防ぎ、停止・unmount で取り消された開始は取得したマイクを閉じる。文字起こしは mount の effect で作り、unmount で `reset()` する
- 送信の合図は最後の区間の末尾の「以上」（`lib/end-of-turn.ts`）。沈黙では送らない。Enter（`sendNow`）は、応答中なら応答の終わりまで待ってから送る（「以上」と同じ）。`evaluate` は区間が文字起こし中か VAD が発話中のあいだは送らず、失敗した区間は飛ばして送る。30 秒で強制的に区切った区間も同じ評価を通る。送った発言は `voice_auto` で、`stt_method` / `stt_latency_ms`（「以上」の区間の終わりから送信まで）を `dialogue_messages` に残す。プロンプトに注入しない値なので `HumanMessage` にも state にも載せない
- 聞き取りカードが最後のメッセージのときは、「以上」で送らずに `onHold` で入力欄へ入れてパネルを閉じる（カードへの回答は取り消せないため）。このとき復元する文字起こしの自動送信の印は付けず、`input_mode = 'voice'` で保存する。鉛筆ボタン（取り消し）もパネルを閉じる
- 声で話しているとき（`conversation.status !== "off"`）と、声の回答を入力欄で確認している間（`restoredTranscript` あり）は、聞き取りカードの代わりに `VoiceIntakePrompt` が問いだけを並べ、冒頭の一文と問いを一度に読み上げる（ADR-011）。確認中も切り替えるのは、`onHold` でパネルが閉じるとカードに戻り、表示が入れ替わるため。読み上げる文面は `intakeSpeechText` で作り、`useChatWebSocket` の speechBus と ▶ の両方が同じ関数を使う（`intake_question` の `content` と文面が違うので、▶ で `msg.content` を読むと保持した音声の文の番号がずれる）。回答は自由文の返信として `extract_intake` が処理する
- `VoicePanel` のキー操作（Enter 送信・Esc 一時停止・Backspace 言い直し）は、入力欄への入力中と dialog / alertdialog / menu の中では無視する。Enter はボタン・リンクにフォーカスがあるときも無視する（そのボタンの操作を奪わないため）
- `ChatInput` は mount 時点で渡された `restoredTranscript` から `transcripts` / `restoredAutoSent` を初期化する。学習・復習の両ページは、送信に成功したときと「声で話す」を始めるときに `restoredTranscript` を捨てる（古い復元が残ると、次に `ChatInput` が mount し直されたときに再適用される）
- 読み上げはクライアントが応答のストリームを文に切り（`lib/speech-text.ts` の `SentenceSplitter`。応答の最初の文が 25 字を超えると 10 字以降の最初の読点で切る）、`POST /api/speech`（JSON: `text`・必須の `dialogue_session_id`・`speed`）へ順に要求する。`speed` は 1 / 1.25 / 1.5 のいずれか（JSON の整数 `1` も受ける）。返りは 24kHz・16bit・モノラルの PCM のストリームで、`useSpeechPlayback` が届いたチャンクを `AudioContext` の時刻軸に隙間なく並べる（同時の要求は 2 件。`inflightRef` の上限）。応答のテキストは `useChatWebSocket` の `speechBus` が `useAssistantSpeech` へ渡す
- 応答は `ChatMessage.speechKey` で識別する。`useChatWebSocket` が応答ごとに発行してメッセージと `speechBus.text(key, text)` の両方に載せ、再開した履歴の AI 応答は `resumed-<セッション ID>-<添字>` になる（セッション ID が無いと、別セッションの同じ位置の応答が保持された音声を取り違える）。再開時は読み上げを止める。取り消しで添字は再利用されるので、添字で応答を指さないこと
- 合成した PCM は `useSpeechPlayback` が `(speechKey, 文の番号)` でページ内に保持する（最大 20 応答）。速度を変えると保持を捨てる。▶（`MessageSpeechButton`）のやり直しは保持を使い、再課金しない。文の番号は `SentenceSplitter` の出力順で、ストリームを読む側（`useAssistantSpeech`。読まない文にも番号を振る）と ▶ の `splitIntoSentences` が同じ分割になることが前提
- `useSpeechPlayback` の unmount の後始末は `AbortController` を作り直す。開発時の Strict Mode が effect を 2 回実行するため、作り直さないと以降の要求がすべて取り消し済みになる
- `sendMessage` は送れたかを返す。`ChatInput` の `onSend` が `false` を返すと、入力欄・文字起こし・自動送信の印を残して案内を出す
- `POST /api/speech` は 1 回 `MAX_SPEECH_CHARS` 文字まで、1 日の上限は `DAILY_SPEECH_CHAR_LIMIT` 文字。成功した分だけ `speech_usages`（文字数）に記録し、`REVIEW_TIMEZONE` の暦日で数える。判定はアトミックではない。外部 API を待つので `DB` 依存を使わない
- `POST /api/speech` は本文を `StreamingResponse` で返す。Langfuse の `synthesize-speech` は `start_speech_trace()` が current にせず作り、ストリームの `finally` で `finish()` する（本文の送信は別タスクで走るため）。使用量は最初のチャンクを得た直後、`StreamingResponse` を返す前に記録する（上流はその時点で課金済みで、本文が始まる前に切断されても数え漏れない）。上流のストリームは `finally` と `BackgroundTask` の両方で閉じる。`BackgroundTask` に渡すのは `async` のラッパー（`close_stream`）で、`stream.aclose` を直接渡すと Starlette が同期関数として threadpool で呼び、await されない
- 環境変数: `SPEECH_MODEL`（既定 `gpt-4o-mini-tts`）・`SPEECH_VOICE`。認証は既存の `OPENAI_API_KEY`
- 自動送信した発言を取り消すと、元の文字起こしと自動送信の印が入力欄の側に復元され、直して送り直すと `raw_transcript` が残り `input_mode` も `voice_auto` のままになる（`lastSentRawRef` / `lastSentAutoRef` → `editingRawTranscript` / `editingAutoSent` → `ChatInput` の `restoredTranscript`）。送り直しを `voice` にすると、訂正のあった発言が `voice_auto` から消えて計測できない
- 読み上げ中・応答中に話し始めたら、`useAssistantSpeech.silence()` で読み上げを止め、その応答の残りを読まない（応答中なら、まだ始まっていない次の応答も）。誤検出を減らすため、読み上げ中だけ発話開始の条件を 300ms に延ばす
- **ブラウザは自動再生を制限する**: `AudioContext` はユーザー操作の中で解錠する。入口は「声で話す」（`useVoiceConversation.start`）と ▶（`playMessage`）。再生の直前に suspended なら `resume()` を最大 300ms 待ち、動かなければその応答の残りを捨てる
- 応答の終わりは `speechBus.end()` で知らせるため、`assistant_message_end` 以外で応答が終わる経路（`error`・`pending_message_rolled_back`）でも `end()` を呼ぶこと。呼ばないと次の応答が丸ごと黙る。応答を読み切らずに捨てる経路（`ws.onclose`・`resetSession`）は残りを読み上げないよう `speechBus.abort()` を呼ぶ（`end()` だと途中の文まで読み上げる）
- 声で話していないときの入力欄のマイク（`useVoiceRecorder`。文字起こしを入力欄に入れて確認してから送る）は残っている。これは `input_mode = 'voice'`
- 上流の TTS が本文の途中で失敗すると、サーバーはログを出して `SpeechError` を再送出し、チャンク転送を異常終了させる。クライアントはその文の保持を捨てて失敗の通知を出す（途切れた文を保持して ▶ が再生しないため）
- 一時停止（`pause`。タブが隠れたときも同じ）はマイクを手放し、再開（`resume`）は `start` と同じ `startingRef` + トークンの経路で開き直す（隠れている間は再開しない。開き直しに失敗したら会話を終える）。一時停止中のパネルは応答を読み上げない（`useAssistantSpeech` の `enabled` は `active` / `starting` のみ）。発話の途中で止めた区間は文字起こしに回すだけで、自動では送らない
- Enter（`sendNow`）の `stt_latency_ms` は Enter を押した時刻から測る（「以上」を言わない送信に、古い区間の終わりからの時間を載せないため）。値は 600000ms で頭打ちにする
- `audio/wav` は 16kHz のみ受け付け、ヘッダーだけ（サンプル 0）は 415（長さを秒数で課金するのでレートがずれると過小・過大に数えるため）

### ノートの埋め込み（pgvector）

- ノートの埋め込みは `note_embeddings`（`note_id` が PK、`vector(1536)`、`model`、`content_hash`）に持つ。入力は topic・summary・content・`note_revisions` の本文を連結したもの（`services/note_embedding.py` の `build_embedding_text`）
- 作り直すのは、ノートの生成（`generate_note`）・復習による更新（`update_note_and_feedback`）・手での本文編集（`PATCH /api/notes/{id}`）の後で、どれも `schedule_note_embedding` でバックグラウンドに回す。`content_hash`（モデル名 + 入力のハッシュ）が同じなら API を呼ばない。失敗してもノートの保存は成功させ、次の更新か `uv run python -m scripts.backfill_note_embeddings` で作り直す。ノートの本文を変える経路を足したら、ここにも呼び出しを足すこと
- 近傍検索は同じユーザー・同じ `model` の埋め込みだけを比べる。モデルを変えたら backfill で作り直す（`find_note_ids_without_embedding` は `model` 違いを未作成として拾う）
- asyncpg に vector 型のコーデックを登録せず、`$n::vector` に `[0.1,...]` の文字列を渡す（`note_embedding_repository._to_vector_literal`）
- **束ね先の候補はベクトルでも入れる**（`services/collection_suggestion.py` の `suggest_collection_by_similarity`）。埋め込みを作り直した直後（`refresh_note_embedding` の末尾）と、`backfill_note_embeddings` の 2 周目で呼ぶ。近い `COLLECTION_SUGGESTION_NEIGHBORS` 件のうち、類似度が `COLLECTION_SUGGESTION_MIN_SIMILARITY` 以上でまとめノートに入っているものを、まとめノートごとに類似度の合計で比べ、最上位の名前を `notes.suggested_collection` に入れる。画面の候補のバナーと「入れない」の操作は、生成時の LLM の候補と共通
- 候補を入れるのは、束ねておらず・候補も無く・`collection_suggestion_dismissed_at` が無いノートだけ（`set_suggested_collection_if_unsuggested` が 1 文で判定する）。生成時の LLM の候補があればそちらを優先する。候補を断ったとき（`clear_suggested_collection`）と、まとめノートから外したとき（`set_collection(None)`）に `collection_suggestion_dismissed_at` を立て、以後は自動で提案しない。これが無いと、断った候補がノートの編集のたびに戻る
- `COLLECTION_SUGGESTION_MIN_SIMILARITY`（既定 0.5）は実データで決めた暫定値で、改善の余地がある。測り方・調整の目安・改善案は `docs/collection-suggestion.md`
- **ノートどうしのつながりの候補も埋め込みで作る**（`services/note_links.py` の `suggest_note_links`）。束ね先の候補と同じく、埋め込みを作り直した直後と `backfill_note_embeddings`（埋め込みのある全ノート）で呼ぶ。同じまとめノートのノートは除き、近い `NOTE_LINK_LIMIT` 件のうち類似度 `NOTE_LINK_MIN_SIMILARITY`（暫定 0.6）以上を `note_links` に `suggested` で入れる。1 組を 1 行で持ち（`note_id_a < note_id_b`）、両方のノートの詳細に出る。作り直しでは類似度だけを更新し、採否（`accepted` / `dismissed`）は変えないので、断った候補は戻らない。下限を下回った未回答の候補は消す。候補を作った後に両方を同じまとめノートに入れたら、未回答の候補は表示しない（行は残す）
- Langfuse には `traced_embedding()` が `embed-note`（generation）として user だけに紐づけて送る
- 環境変数: `EMBEDDING_MODEL`（既定 `text-embedding-3-small`）。次元数 `EMBEDDING_DIMENSIONS` はマイグレーションの `vector(1536)` と一致させる

### Langfuse トレース

- 送出は `observability/langfuse_tracing.py` に閉じている。クライアントは `main.py` の lifespan で `init_tracing()` / `shutdown_tracing()`（後者を省くと終了間際のトレースがバッチ送出されずに落ちる）
- 粒度は **1ターン＝1 trace・1対話セッション＝1 Langfuse session**。グラフは `interrupt_before` で毎ターン中断するため、実行の切れ目がそのままターンの境界になる
- グラフ実行は `traced_graph_run()` で自前の root span に包む。LangGraph の実行をそのまま root にすると trace の入出力が `LearningState` 丸ごと（かつ再開ターンでは入力 `None`）になり、一覧・評価器から読めないため。root span にはユーザー発話と応答だけを載せる
- `CallbackHandler` は root span が active な間に生成する必要がある（生成時点の trace context を引き継ぐため）。`build_graph_config()` が返す config に callbacks は入っておらず、`traced_graph_run()` が実行時に足す
- trace 名（`respond-to-user` 等）はダッシュボード・評価器の参照キーになるため、ID やターン番号を混ぜない。変更は破壊的変更として扱う
- `aget_state` / `aupdate_state` はノードを実行しないので callbacks を付けない（付けると中身のない trace が量産される）
- 環境変数: `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`（未設定なら送出は自動的に無効）・`LANGFUSE_BASE_URL`・`LANGFUSE_TRACING_ENVIRONMENT`（既定 `development`）
- **LLM 観測は Langfuse に一本化している**（自前実装の DB テーブル `run_traces` と `measured_node` / `measured_ainvoke` は廃止）。ノードのレイテンシもトークン数も Langfuse 側にしか無いので、集計・eval のデータ源は Langfuse API を使う
- ノードが LLM を複数回呼ぶ場合（`generate_note` は最大3回（まとめノートの候補 `suggest-collection` を含む。出典が空で既存のまとめノートも無ければ呼ばない）、`generate_feedback` は3回（`analyze-dialogue` と `generate-aspect-map` を並行に走らせ、続けて `generate-feedback-scores`）、`update_note_and_feedback` は3回（`revise-note` と `append-review-addendum` は手での編集の有無でどちらか一方）、`learning_dialogue` は旧経路が dialogue intent 時のみ、地図駆動は毎ターン、事前分析分を含め2回、`review_dialogue` は事前分析（`review-turn-analysis`）と応答の2回（`confirmed` のターンは事前分析の1回）、`learning_start` は聞き取りカード生成の1回（`run_name` なし）、`finish_synthesis` は1回（`run_name` なし）、聞き取りのターンは常に完了ターンで、カード回答なら `generate-depth-map` を含め2回、自由文の返信なら `extract-intake` も含め3回（学習開始の声かけは事前分析を通さない））だけ `config={"run_name": "..."}` で呼び出しを識別する（`generate-note-content` / `estimate-category` / `generate-aspect-map` / `analyze-dialogue` / `turn-analysis` / `map-turn-analysis` / `extract-intake` / `generate-depth-map` など）。1ノード1呼び出しの対話ノードには付けない（ノードスパン名と二重になる）
- **プロンプト本文の同一性は `prompt_version` ではなく `prompt_fingerprint`（質問生成 + 事前分析プロンプトの内容ハッシュ）で判定する**。`prompt_version` は手で維持するラベルなので、上げ忘れ・振り直しで本文との対応が崩れる。実際に 2026-08-04 以前の trace は `generate_question@v1` と `@v2` の 2 ラベルに割れているが本文は同一で、版ラベルで絞ると取りこぼす（`@v2` を欠番にして現行を `@v3` にしたのはこのため）
- **`prompt_fingerprint` は経路ごとに別の値を持つ**。旧経路の質問生成は `PROMPT_FINGERPRINT`（`graph/prompts/question.py`）、地図駆動の応答生成は `MAP_PROMPT_FINGERPRINT`（`graph/prompts/map_question.py`。地図の事前分析を含む）、聞き取りカード・抽出・学習開始の声かけ・深さの地図生成は `INTAKE_PROMPT_FINGERPRINT`（`graph/prompts/intake.py`）、つながりの対話と下書きは `SYNTHESIS_PROMPT_FINGERPRINT`。metadata のキーはどれも `prompt_fingerprint` なので、値で経路を見分ける。地図駆動のプロンプトは旧経路の本文・応答例を流用しているため、旧経路のプロンプトを直すと `MAP_PROMPT_FINGERPRINT` も動く（逆は動かない）。深さの地図は state に保存されるので、ターンの再現に効くのは `MAP_PROMPT_FINGERPRINT` だけ
- **`config={"metadata": ...}` を渡しても trace 属性（session / user / tags）は落ちない**が、それは冗長性に支えられている。`ensure_config` は contextvar 側の metadata を**マージせず置換**するため、`build_graph_config()` が入れている `langfuse_*` キーはその observation から消える。それでも属性が付くのは `traced_graph_run()` が `propagate_attributes()` で OTEL レベルにも同じ属性を伝播しているため（切り分け実験で両経路が独立に機能することを確認済み）。**`traced_graph_run` の外でグラフや LLM を実行しつつ metadata を上書きすると、session グルーピングが静かに壊れる**
- まとめの下書きの生成（`POST /api/collections/{id}/synthesis`）はグラフの外なので、`traced_synthesis()` が `generate-collection-synthesis` の span で包み、`CallbackHandler` で LLM 呼び出しを記録する。session は持たず user と `synthesis` タグだけを付ける。プロンプトの同一性は `SYNTHESIS_PROMPT_FINGERPRINT`（`graph/prompts/synthesis.py`）

### フロントエンドのパターン

- `use-chat-websocket.ts`: 接続ライフサイクル・メッセージ型振り分けを一元管理
- **WebSocket は想定外の切断で自動的につなぎ直す**（`useChatWebSocket`）: サーバーは放置で切らないが、uvicorn の ping タイムアウト（PC のスリープ・タブの凍結）、`fastapi dev` のリロード、デプロイで切れる。`learning` / `review` はトークンを取り直して `resume_session` を送り（間隔を空けて最大 5 回、タブの前面復帰と `online` では回数をリセットして即座に試す）、`synthesis` は再開できないのでエラーを出す。`end_session` の後にサーバーが閉じるのは正常な終了なので、`session_ended` を受けた後の切断では何もしない。サーバー側から接続を閉じる経路を足したら、それが再接続の対象になるか確かめること
- `fetchAPI()`: 全 REST 呼び出しはここを経由（JWT ヘッダー付与、エラーハンドリング）
- `NavbarSlotContext`: レイアウト内でナビバーに動的コンテンツを挿入するポータルパターン
- チャットのメッセージ本文は `Markdown` の `variant="chat"`（`remark-breaks` で単一改行を保持・`rehype-highlight` でコードをハイライト）で描画。ストリーミング中は `closeOpenCodeFence()` で未閉じフェンスを補ってから渡す（`notes`/`review` の `default`/`article` variant とは別系統）
- コピーは各メッセージ単位（`MessageCopyButton` が `msg.content` 全文をコピー）。未フェンスの貼り付けコードでも全文コピーできるよう、コードブロック単位ではなくメッセージ単位にしている
- 学習中の進捗表示は `LearningProgress.aspects`（観点名・中核か・到達段階）から観点ごとのパネルを描く。サーバーは核心の問いの本文と観点の `id` を送らない（AI がこれから問う内容を画面で先出ししないため。開発者ツールからも見せない）。段階の文言と通知の判定はクライアントの `lib/progress.ts` が持つ。聞き取りで得た目的・教材・今の理解は `LearningProgress.intake` で送り、観点マップの先頭に表示専用で出す（state の `learning_goal` / `learning_source` / `prior_knowledge` が源なので、自由文の返信から抽出した値も載る。3 項目とも空なら `None`）
- **ノートの観点マップの ID は保存済み JSON の並び順から振る**（`graph/aspect_map.py` の `with_aspect_ids`。`a1` / `a1-2`。API の `NoteResponse.aspect_map` が付けて返す）。`feedbacks.improvement_items`（JSONB。`improvements` の行と 1:1）がこの ID で改善点と観点を結びつけるので、保存済みの `notes.aspect_map` を並べ替え・作り直す経路を足すときは結びつきも作り直すこと。学習の観点マップは改善点と結びつけるため、`generate_note` ではなく `generate_feedback` が対話分析と並行に作って保存する（失敗したら結びつけずにフィードバックだけ保存する）。学習中の深さの地図（`depth_map`）の ID はクライアントへ送らないが、ノートの観点マップの ID は学習の後に使うだけで内容を含まないので送ってよい。LLM が返した `aspect_id` は観点マップに実在するものだけを残す（`link_improvements`）
- **ノート本文は学習者が説明した内容と AI の補足を分ける**: 任意の節 `## AIの補足`（「重要なポイント」と「まだ曖昧な点」の間）に、学習者が自分の言葉で説明していない用語・定義を置き、「学んだこと」「重要なポイント」には書かない。生成（`GENERATE_NOTE_PROMPT`）・改訂（`UPDATE_NOTE_PROMPT`。復習で説明できた項目は「学んだこと」へ移す）・復習の追記（`APPEND_REVIEW_PROMPT`）・フィードバック（`GENERATE_FEEDBACK_PROMPT`。良かった点の根拠にしない）の 4 つで同じ区別を使う。節名を変えるときは 4 つをそろえる
- **学習の前提はノート作成時に `notes.intake`（JSONB）へ保存し、ノート詳細の観点マップ（`NoteAspectMap`）の先頭に出す**: 値は `generate_note` が state から `build_intake_summary`（`graph/intake_summary.py`。学習中の進捗と同じ正規化）で組み、3 項目とも空なら NULL。復習セッション（`update_note_and_feedback`）は触らない。聞き取りを導入する前のノートと、この機能より前のノートはバックフィルしない（チェックポイントは前提の正本にならない）ので `intake` が NULL のまま表示しない。`NoteAspectMap` は観点が空だとセクションごと出さないため、観点マップの生成中・失敗時は前提も出ない
- **トピック訂正の確認は聞き取りカードと同じ経路で出す**: サーバーの `topic_correction_question` を `ChatMessage.topicCorrectionCard` に載せ、最後のメッセージのときだけ `TopicCorrectionConfirm`（「はい、変更する」「いいえ」）を出す。回答は `sendMessage` の末尾の引数で `topic_correction_answer` として送り、吹き出しには `topicCorrectionAnswerText` の文を出す（`content` は LLM が読むので変えない）。再開時は `dialogue_messages.topic_correction_card` / `topic_correction_answer` から復元する。回答の発言は取り消せないのでやり直しボタンを出さない。確認が最後のメッセージのあいだは、聞き取りカードと同じく声の自動送信を止める（`choicePending`）。声で「はい」と言っても自由文として送られ、サーバーは「いいえ」扱いにするため
- **ヘッダーのトピック編集は `NavbarTopic` の `onEdit` で出す**: 鉛筆を出すのは接続中・応答の生成中でない・未終了・`progress.aspects` が空でないときだけ（復習の画面は `onEdit` を渡さない）。確定の前に `AlertDialog` で地図の作り直しと到達度のリセットを伝える。送った発言は `ChatMessage.topicEdit` で 1 行の表示（`TopicEditedNotice`）にし、やり直しボタンを出さない。ナビバーのトピック名は `assistant_message_end.topic` が届いてから変わる（送った時点では変えない）。サーバーが拒否したら `topic_edit_rejected` で 1 行の表示を消し、入力欄の下書きには触れない
- **セッションの終了ボタンは学習・復習とも `EndSessionButton`**（常にラベル付き。学習「ノートを作成」、復習「ノートを更新」）。応答の下の確認は `EndSessionConfirm`、ノートを作らずに終えたセッションの表示は `SessionEndedNotice`。確認が出ていても声の自動送信は止めない（声で再び終える意志を伝えると確定するため。聞き取りカード・トピック訂正の確認とは違う）。`endSession` は送れたかを返し、送れなかったときは終了ボタンを押し直せる
- **UI を作る・変えるときは先に `docs/design/ui-guidelines.md` を読む**: アイコンとラベル・ツールチップ・状態の網羅・動き・アクセシビリティなど、判断が要る規則の正本（トークンと lint で守る規則はこの節と ADR-009）
- **`TooltipProvider` はルート（`app/layout.tsx`）に 1 つだけ置く**: 部品ごとに置くと、続けて別のツールチップに乗せたときの遅延の省略が効かない。`Tooltip` を使う部品のテストは `vitest.setup.ts` が `render` を `TooltipProvider` で包むので、テスト側で包まない。アイコンだけのボタンは `aria-label` を付けて `TooltipLabel` で説明する（`button` / `Button` / `a` / `Link` / `div` / `span` の `title` 属性は ESLint が error にする）。メッセージの操作ボタンは `MessageActionButton`
- **色・文字サイズ・重なり順は名前で書く**: `bg-blue-500` のような Tailwind の色名、`text-[10px]`、`z-50`、`h-4 w-4` は書かない（ESLint が error にする。`components/ui/` の shadcn 生成物はサイズ・z-index のルールだけ除外）。色は `app/globals.css` のトークン（`brand` / `success` / `warning` / `caution` / `destructive` / `chart-1`〜`5`。それぞれ `-soft`・`-text` あり）、文字サイズは `text-3xs` / `text-2xs` / `text-prose`、アイコンは `size-N`、重なり順は `z-raised` / `z-menu` / `z-drawer` / `z-overlay`。基調色は `--brand` で、shadcn の `--primary`（白黒）とは別に持つ。目立たせたい塗りのボタンは `--brand-strong`（`--brand` より一段濃い。ダークでは暗くなりすぎて黒に見えないよう、ライトより明るい値）、背景が常に濃い青のところ（LP の CTA）の文字は `--brand-deep`。濃さを変えたいときは `globals.css` のこの値を直し、個別のクラスで色を上書きしない。ライト・ダークの切り替えは変数側で行うので `dark:` で色を上書きしない
- **意味と見た目の対応は 1 か所に置く**: トーンは `lib/tone.ts`、緊急度・観点のカバー状況・フィードバックの種類は `lib/status-display.ts`（`getUrgency` を含む）。復習カードの左ボーダーだけを色付ける `border-l-*` のように、`TONE_CLASSES` の `border`（四辺の色）では足りない場合は `status-display.ts` 側に別に持つ
- **共通部品を先に探す**: 読み込み表示は `Spinner`（`animate-spin` を直接書かない。テストが検査する）と全画面の `LoadingOverlay`、空表示は `EmptyState`。`Spinner` は既定で `aria-hidden`、`label` を渡したときだけ `role="status"` を持つ（`role="status"` の入れ子は `getByRole("status")` を重複させる）。標準的なボタンは `Button`（強調は `variant="brand"`）を使う
- **直書きを許す例外**: `app/opengraph-image.tsx` と `app/global-error.tsx` の hex（CSS 変数が効かない環境で描画する。`opengraph-image.tsx` の色は `--brand-*` の blue と揃える）、`lib/email/otp-email.ts` の hex（メールでは CSS 変数が効かない。色は `--brand` と揃える）、ロゴの hex（`app/icon.svg`・`app/apple-icon.tsx`・`components/brand/app-logo.tsx`。ロゴの色はテーマで変えない。`--brand` はダークで明るい青に変わるので使わない。`app-logo.tsx` の図形と色は `icon.svg` と一致させ、テストが検査する）、`globals.css` のコードハイライト、暗幕の `bg-black/*`、`text-white` / `bg-white`
- **トークンの見本**: 開発中は `/design-tokens` で全トークンと部品をライト・ダークで確認できる（本番では 404）。トークンを足したら `__tests__/styles/design-tokens.test.ts` の一覧と見本ページにも足す
- **UI の確認用に作った一時的な見本ページ（`app/<名前>-preview/`）は、コミットと PR が終わったら削除する**: main に残さない。コミットには含めず、この節にも一覧を足さない
- **アカウント欄（アイコン・ユーザー名・テーマ切り替え）はサイドバーの一番下**（`SidebarAccount`）: 折りたたみ中はアイコンだけ、開いているときは左からアイコン・名前・テーマ切り替え。ナビバーは中央のスロットだけを持つ。アイコンが画面の左下に来るため、Next.js の開発用インジケーター（既定は左下でクリックを横取りする）を `next.config.ts` の `devIndicators.position` で右上へ動かしている。左下に固定要素を足すときも同じ衝突に注意

---

## テスト

| 種別 | 場所 | フレームワーク | カバレッジ目標 |
|------|------|--------------|--------------|
| バックエンド unit | `server/tests/unit/` | pytest | 75% |
| バックエンド integration | `server/tests/integration/` | pytest | - |
| フロントエンド | `client/__tests__/` | Vitest | - |

- `asyncio_mode = "auto"` のため `@pytest.mark.asyncio` 不要
- DB を使うテストは実 PostgreSQL に接続（モック禁止）
- テスト用 DB: `make test-db`

---

## CI（GitHub Actions）

PR マージ前に全通過が必須:

- `server-lint`: ruff check / format
- `server-typecheck`: mypy（strict）
- `server-test`: pytest（実 DB）
- `client-lint`: eslint + `tsc --noEmit`
- `client-test`: vitest
- `secret-scan`: Gitleaks

---

## コード規約

### コメント（言語共通）

**既定は「書かない」**。残してよいのは、**コードからも周辺ファイルからも復元できない事実**だけ ——
外部仕様・ライブラリの癖・ブラウザやフォーマットの挙動・ファイルをまたぐ値の一致制約。

**「なぜ」を書いてあれば残る、ではない。** 以下は理由が書かれていても削除対象:

| 削除対象 | 例 |
| --- | --- |
| コードの言い換え | `assert record is not None  # INSERT ... RETURNING は必ず1行返す`、`if TAG in tags: continue` の上に付けた「内部呼び出しの出力を流さない」 |
| **CLAUDE.md に書いてある知識の再掲** | `GRAPH_VERSION` の用途、`turn_analysis` に `None` を明示する理由、`INTERNAL_LLM_TAG`、`REVIEW_TIMEZONE` の暦日判定、`completed_today` の存在理由、Langfuse の `CallbackHandler` を root span 内で生成する理由 |
| 定数・環境変数への説明 | `core/config.py` の各変数（名前と既定値で足りる） |
| テスト内の手続き説明 | テスト名・docstring・アサーションと重複する行、`# 現在時刻より過去` のような値の注釈 |
| 型エイリアスの背景解説 | 他の型との対応表など、使う側が知らなくても正しく書けるもの |
| 直後の分岐・例外メッセージで自明な意図 | `raise ValueError("Invalid storage key")` の上の「パストラバーサルを防ぐ」 |

**プロジェクト規約の正本は CLAUDE.md**。コード側に複製しないこと（二重管理になり、CLAUDE.md を直しても
コメントが古いまま残る）。逆に、コードから読み取れない制約に気づいたらコメントではなくこの CLAUDE.md へ書く。

残す場合も**最短で書く**。修飾語を削って 1〜2 行に収める。

- 残す例: `# 保存 mime は実体と一致する保証がないため、ブラウザの MIME スニッフィングを抑止する（多層防御）`（ブラウザ挙動）/
  `core/database.py` の `DBConnection` の型注記（asyncpg の癖）/ `# WebP は RIFF コンテナ: "RIFF"<4byte size>"WEBP"`（フォーマット仕様）/
  「値はプロンプト本文（`graph/prompts/review.py`）の指示と一致させる」（ファイルをまたぐ制約）
- 判断に迷ったら書かない。コメントで補うより、命名と関数分割でコード自体を読めるようにする。

### Python（Ruff + mypy strict）
- 行長: 119 文字、Python 3.13 ターゲット
- ルール: E, W, F, I, B, UP
- `pydantic.mypy` プラグイン使用

### TypeScript
- ESLint + Prettier（`.ts`/`.tsx` はコミット時に自動フォーマット）
- strict モード

### pre-commit フック（`uv run pre-commit install` で有効化）
- ruff check + format（server/）
- mypy（server/）
- prettier（client/ の .ts/.tsx）

### Issue
- `.github/ISSUE_TEMPLATE/` の種類（bug / feature / refactor / chore / docs / test / research）から選び、その節の構成・タイトルの接頭辞・ラベルに従って書く。`gh issue create` は `--template` を付けないとテンプレートを使わないので、本文を構成どおりに組み立て、`--label` も付ける
- 新機能も既存機能の改善も `feature`（`enhancement` は使わない）。実装せず調べることから始めるものは `research`

---

## 注意事項（ハマりポイント）

> **このセクションの育て方**: 実装中に、コードを読むだけでは分からない制約・ライブラリの癖・型の落とし穴（例: 下記の asyncpg Pool/Connection 型不一致）に直面し、それを考慮して実装・修正したときは、その教訓をここへ追記することを提案する。判断基準は「コードから読み取れることは書かない。『なぜ』『制約』だけ書く」。これにより、以降の実装が同じ問題を最初から考慮できるようにする。

- **DB イメージは pgvector 入り**: `CREATE EXTENSION vector` のマイグレーションがあるため、素の `postgres:17` では `alembic upgrade head` が失敗する。既存のローカル DB は `docker compose up -d db db_test` で `pgvector/pgvector:pg17` に作り直す（同じ PostgreSQL 17 なのでボリュームはそのまま使える）。本番（Railway）の Postgres も拡張を入れられることが前提
- **フィードバックは 1 ノートに複数行（評価の履歴）**: 学習の `generate_feedback` も復習の `update_note_and_feedback` も `feedbacks` へ追記する（#152 の上書きは廃止）。最新の評価は `find_by_note_id`（`created_at` の昇順）の末尾で、復習の重点（`prior_improvements`）・`feedback_generated`・セッション詳細はこれを `feedbacks[-1]` で読む。並び順を変えるとこれらが古い評価を読む。`improvement_items` が NULL の行は結びつきを導入する前のもので、改善点の本文だけを今までどおり表示する
- **マイグレーション順序**: `alembic upgrade head` の前に `client/better-auth_migrations/*.sql` を適用すること（外部キー制約あり）
- **BetterAuth スキーマは静的SQLで `auth.ts` と自動同期しない**: `client/better-auth_migrations/*.sql` は生成時点のスナップショット。`client/lib/auth.ts` のプラグイン（例: `jwt()` は `jwks` テーブルを要求）を追加・変更したら `npx @better-auth/cli generate --config lib/auth.ts` で再生成してコミットすること。漏れると新環境で `relation "jwks"/"user" does not exist` になる（過去に `jwks` 欠落で認証が落ちた）
- **認証まわりの `import "server-only"` は `npx @better-auth/cli generate --config lib/auth.ts` の読み込みを失敗させる**: `lib/auth.ts` から辿れる `lib/auth-otp.ts` → `lib/dev-auth.ts` と `lib/email/send-email.ts` が持つため。スナップショットを再生成するときは、これらの import を一時的に外す（または `server-only` をスタブする）。実行後は必ず元に戻すこと
- **`better-auth_migrations/` は常にスナップショット1ファイルのみに保つ**: `generate` が出すのは差分ではなくフルスキーマで、実行するたび新しいタイムスタンプ名のファイルが増える。再生成したら古いファイルを削除すること。複数残すと `make setup` のループが古い方を先に適用し、新しい方は全文 `already exists` で失敗する（`-v ON_ERROR_STOP=1` を入れる前は psql が exit 0 を返すため、古いスキーマのまま成功したように見えていた）。`migrate` サブコマンドは `client/.env.local` の `DATABASE_URL` へ直接 DDL を打つので、適用先の確認なしに使わない
- **聞き取りカードへの回答は取り消させない**: 取り消すと `intake_complete=True` のままカードが最後のメッセージに戻り、再回答が地図駆動の経路で処理される。`_handle_cancel_last_message` が `intake_answers` 付きの発言と、カード直後の自由文の返信の両方を拒否し、クライアントも鉛筆ボタンを出さない
- **Node 25 以降は組み込みの `localStorage` が jsdom のものを覆い隠す**: `--localstorage-file` が無いと `window.localStorage` が使えず、`localStorage` を触るテストが `Cannot read properties of undefined` で落ちる。`client/vitest.setup.ts` がメモリ上の `Storage` で補うので、`localStorage` を使うテストにテスト側の回避は要らない（補うのは `clear` が使えないときだけで、本物の `Storage` と違いプロパティ代入と `storage` イベントは再現しない）。Node のバージョンを上げるときは `.nvmrc`・`engines`・CI・`client/Dockerfile` / `Dockerfile.dev`・README をそろえる
- **スタック状セッション**: サーバー起動時に `reset_stuck_generations()` が自動実行される（`main.py` の `lifespan` 参照）
- **LangGraph 永続化**: チェックポイントは DB に保存されるため、ローカル開発中にスキーマ変更するとチェックポイントとの不整合が起きる場合がある
- **DB テーブル**: `notes`, `dialogue_sessions`, `dialogue_messages`, `feedbacks`, `review_schedules` が主要テーブル。BetterAuth テーブル（`user`, `account`, `session` 等）も同一 DB に存在し、外部キー制約によるカスケード削除あり
- **CORS**: `CORS_ORIGINS` 環境変数でカンマ区切りで複数指定可能（デフォルト `http://localhost:3000`）
- **外部 API を長く待つ REST ルートでは `DB` 依存を使わない**: `get_db` はリクエストの間ずっとプール（既定 最大 10）からコネクションを借り続ける。文字起こしのように数十秒かかる呼び出しが数件重なると、他の全エンドポイントと WebSocket が `pool.acquire()` で待たされる。`get_pool()` から必要なクエリの間だけ `acquire()` し、外部呼び出しの前に手放す（`api/routes/transcription.py`）
- **multipart のアップロードはハンドラより前に全量受信される**: FastAPI は `UploadFile` を解決する前に multipart 全体をパースし、Starlette は 1 MiB を超えるファイルを一時ファイルへ spool する（リクエスト終了で削除）。`MAX_AUDIO_BYTES` の判定はその後なので、巨大なアップロードを途中で止められない。本番ではリバースプロキシのボディ上限で止めること（#128）
- **ストリーミング対象ノード内の内部 LLM 呼び出しには `INTERNAL_LLM_TAG` を付ける**: WebSocket の `_stream_ai_response` は `stream_mode="messages"` を「ノード名が `_STREAMING_NODES` に含まれるか」だけでフィルタするため、対象ノード（例: `learning_dialogue`）の中で行う structured output 等の追加 LLM 呼び出しの出力（生 JSON）もそのままクライアントへ流れてしまう。内部呼び出しの runnable に `.with_config(tags=[INTERNAL_LLM_TAG])`（`graph/llm.py`）を付与すること。chat.py 側がこのタグ付きチャンクを除外する
- **「今日」の暦日判定はユーザーTZで行う**: 復習スケジュールの時刻列は `TIMESTAMPTZ`（UTC 保持）。「今日復習を完了した件数」のような暦日集計を `last_reviewed_at::date = CURRENT_DATE` でやるとサーバーの稼働 TZ 次第で日付境界がずれる。`(last_reviewed_at AT TIME ZONE $tz)::date = (NOW() AT TIME ZONE $tz)::date` のようにユーザーTZ（`REVIEW_TIMEZONE`、既定 `Asia/Tokyo`）へ変換してから比較する。なお「期限到来済みか」の判定（`next_review_at <= NOW()`）は瞬間の前後比較なので TZ 非依存で問題ない。暦日に丸める集計だけが TZ 依存。
- **復習の開始で重点の観点を選べる**: `start_review.focus_aspect_ids`（省略可）で、最新のフィードバックの改善点のうち結びつく観点を絞る。絞り込みと重点の観点名は `services/review_focus.py` の `build_review_focus` が決め、改善点は `prior_improvements`、観点名は `review_focus_aspects`（学習の `focus_aspects` とは別。区切りの提案の判定には使わない）に入れてプロンプトへ注入する。省略・観点マップが無い・結びつきが無い行では、今までどおり最新の改善点を全部入れる。選ばれなかった観点の改善点は入れない（観点に結びついていない改善点は常に入れる）
- **復習完了はダッシュボードに残さず消す**: ダッシュボード（`GET /api/review-schedules`）は `next_review_at <= NOW()` かつ `status IN ('pending','overdue')` の未到来分だけを返す。実際の復習完了（review セッションの `update_note_and_feedback` → `_advance_review_schedule`）で `next_review_at` が将来へ進むと自動的に一覧から消える。フロントで「開いた＝復習済み」のような疑似状態を持って表示を残さない（次回到来まで非表示が正）。当日の進捗バーに必要な「当日完了件数」は一覧から消えるため `completed_today` として別途集計して返している
- **`review_count` は完了した復習の回数で、`calculate_next_review` には完了後の回数を渡す**: 学習直後は 0（翌日）、1 回目の復習の後は 1（3 日後）。学習（`generate_feedback`）はスケジュールを作るだけで回数に数えない。ダッシュボードの「N 回目」は次に行う復習なので `review_count + 1`
- **期限前の復習はスケジュールを動かさない**: 次の復習日が `REVIEW_TIMEZONE` の暦日で今日より後なら、`_advance_review_schedule` は回数・次の復習日・`last_reviewed_at` のどれも変えない（`is_early_review`）。まだ覚えているうちの復習を 1 回と数えると、定着していないのに間隔だけ伸びるため。フィードバックの履歴には残り、`completed_today` には数えない
- **golden の deterministic assertion は `check_fingerprint`（`evals/checks.py` の実装の内容ハッシュ）を持たせる**: `check:` の名前だけでは golden から実装を辿れず、検出フレーズや判定ロジックを変えても record は無変更で通る。ずれたまま採点すると `human_verdicts` との不一致が judge の誤りとして現れ、**judge のせいでない failure を judge のせいだと誤診する**。値が動いたら criterion を読み直してから転記すること（実装が変わった記録であって、criterion がまだ実装を正しく説明しているかは人間しか判断できない）
- **`LearningState` のキー削除・改名は `GRAPH_VERSION` を上げる**（トポロジー不変でも例外）: `should_interrupt()`（`_algo.py`）はチェックポイントに永続化された `channel_versions` を丸ごと参照するが、`versions_seen[INTERRUPT]` の更新（`_loop.py`）は現在のグラフが宣言しているチャンネルにしか及ばない。宣言から消えたキーの version は永遠に「済」にならず、そのキーに値を持つ既存スレッドは `learning_dialogue` / `review_dialogue` の直前で毎ターン再中断し続け、進行不能になる
- **再開時に「応答が返らないまま残ったユーザーメッセージ」を巻き戻す**: 応答生成の途中で切断すると、DB と state にユーザーメッセージだけが残る。放置するとユーザーは同じ内容を再送するしかなく、履歴に同一発言が二重に残る（実セッションで発生）。`_handle_resume_session` の `_rollback_unanswered_turn()` が state（`RemoveMessage`）と DB の両方から取り除き、`pending_message_rolled_back` でクライアントの入力欄へ戻す。対話ノードは走っていないので `turn_count` は触らない。state への反映前に落ちた場合は DB 側にだけ残るので、そちらも同じ関数が拾う。聞き取りカードへの回答は整形済みの本文から構造化された回答を再現できないため、`pending_message_rolled_back` の `content` を空文字にする（カードが再び最後のメッセージになり、そこから答え直す）
- **対話ノードは `prepare_turn`（事前分析）と `respond`（応答生成）に分かれている**: eval が保存済みの決定を注入して応答生成だけ再実行できるようにするため（`--replay-mode pinned`）。分析の揺れとプロンプト改訂の効果を切り分けられなくなるので、この分割を戻さないこと。旧経路の `learning_dialogue` は両方を順に呼ぶだけ（地図駆動にも同じ `prepare_map_turn` / `respond_map` の分割がある）
- **eval の judge カスケードは screen の fail だけを confirm に回す**: エスカレーション条件（`should_escalate`）は `holds` ではなく polarity 適用後の verdict で判定する。screen（既定 Haiku）の FN（欠陥を pass と言う誤り）は confirm（既定 Opus）に届かないため最終判定に残る。scoring の校正ゲートは screen 単体の TPR も出すので、そこを見て「カスケードで救えない」誤りが無いか確認すること
- **`_handle_cancel_last_message` の `is_session_ended` の拒否は、メインのループが終了後に抜けるので今は届かない**: 防御として残してあるだけで、終了後の取り消しを拒否する根拠にはならない
- **まとめノート（`note_collections`）とカテゴリー（`notes.category`）は別の概念**: カテゴリーは分野（「OS」など）で一覧の絞り込み用、まとめノートはまとめの単位（本 1 冊など）。画面では「まとめノート」と呼び、コード上の名前は `collection` のまま（「テーマ」は配色の切り替えと紛らわしいため画面では使わない）。まとめノートの候補（`notes.suggested_collection`）は生成時の推定で、ユーザーが確定するまで `collection_id` を入れない
- **まとめの下書きが古いかは内容ハッシュで判定する**: `notes.updated_at` は観点マップの保存でも動くので使えない。`notes.content` と `note_revisions` の本文を順に連結した SHA-256 を、生成時に `collection_syntheses.source_notes` へ保存し、表示時に比べる（`services/collection_synthesis.py`）。ノートの本文を変える経路を足したら、ハッシュの入力に含まれているか確かめること
- **地図の事前分析に渡す観点の一覧では、観点名に印を付けない**: LLM は観点を返すとき、一覧に見えた文字列を名前ごと写す。以前は中核観点を「〇〇（中核）」と書いていたため、LLM が `〇〇（中核）` を返し、`resolve_aspect` がどの観点とも一致させられず、中核でない重複の観点（id `〇〇-中核`）を地図に足していた。進捗がすべて重複の側に付き、中核観点が 0 のまま区切りの提案が出なくなる。中核かどうかは `_format_aspect_list` で名前と別の欄に書き、`resolve_aspect` も末尾の「（中核）」を除いて照合する。この修正より前のセッションと capture の地図には重複の観点が残っている
