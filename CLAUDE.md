# CLAUDE.md

## プロジェクト概要

「プロテジェ効果」（教えることで学ぶ）を活用した AI 学習アプリ。ユーザーが LLM と対話しながら学習し、ノート・フィードバック・復習スケジュールが自動生成される。

- **client/**: Next.js 16 (App Router) + React 19 + TypeScript
- **server/**: Python 3.13 + FastAPI + LangGraph
- **DB**: PostgreSQL 17（asyncpg で非同期アクセス、ORM 不使用）
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
uv run python -m evals.eval --mode regression --emit-jsonl <path>  # regression の生成を正本へ追記
uv run python -m evals.eval --checkpoint-dir evals/reports/<name>  # 生成・採点の保存先を固定し、再開できるようにする（既定は自動生成）

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
> 変わるため。スキップした理由は report に出る。
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
│   ├── builder.py             # グラフ定義・route_after_dialogue
│   ├── state.py               # LearningState TypedDict
│   ├── nodes/                 # learning_start, learning_dialogue, generate_note, generate_feedback, update_note_and_feedback
│   └── prompts/               # タスク別プロンプト（intake, depth_map, map_question, analysis, note, feedback, review, question）
├── observability/             # langfuse_tracing.py（Langfuse へのトレース送出）
├── repositories/              # SQL-first データアクセス（asyncpg 直接）
├── schemas/                   # Pydantic モデル（リクエスト/レスポンス）
├── storage/                   # 対話添付のオブジェクトストレージ抽象（local 実装、S3 は #128 で追加）
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
│   └── utils.ts
└── __tests__/                 # Vitest テスト
```

---

## アーキテクチャ詳細

### LangGraph ワークフロー

```
learning_start → learning_dialogue（対話継続中はループ）
  ├─ session_type="learning" → generate_note → generate_feedback → END
  └─ session_type="review"   → update_note_and_feedback → END
```

- 分岐は `graph/builder.py` の `route_after_dialogue` が担当：`should_generate_note` が立つまで `learning_dialogue` をループ、立った後 `session_type` で `generate_note` / `update_note_and_feedback` に分岐
- レビューセッション: 既存ノートをプロンプトに注入し、`update_note_and_feedback` でノート・フィードバックを更新（`generate_note` / `generate_feedback` は通らない）
- `interrupt_before=["learning_dialogue"]` でユーザー入力待ちのため毎ターン中断する（再開はチェックポイントから）
- ノードスパン・LLM 生成の計測は Langfuse が自動で行う（`observability/langfuse_tracing.py`）。詳細は「Langfuse トレース」節
- グラフ状態は `langgraph-checkpoint-postgres` で DB に永続化
- `LearningState` は `session_type`（`"learning"` / `"review"`）で分岐
- **プロンプトを変える決定値は state に残す**。`learning_dialogue` の事前分析が決める `response_mode` / `selected_aspect`（`turn_analysis`）は、無いと会話履歴と state からターンを再現できず eval の regression が成立しない。同じ理由で、新しく「プロンプトに注入するがどこにも保存しない値」を作らないこと
- **区切りの提案（`wrap_up`）は LLM ではなく `covered_aspects` から決定的に決める**（`graph/coverage.py` の `coverage_progress`）。exemplified 以上の観点が `WRAP_UP_MIN_ASPECTS` 個（`focus_aspects` 指定時はその全観点）に届き、誤りが無く、未提案（`wrap_up_offered`）のターンだけ質問をやめて区切りを提案する。提案は 1 セッション 1 回で、終了はさせない。`focus_aspects` は判定上 `covered_aspects` と**表記の完全一致**で照合するため、事前分析が表記を揺らすと完了しない。なお `cancel_last_message` は `covered_aspects` / `wrap_up_offered` を巻き戻さない
- **毎ターン置き換わる state フィールドは、値が無いターンにも明示的に `None` を書く**。LangGraph はキーを省いた更新では前ターンの値を保持するため、書かないとチェックポイント履歴を辿る側（eval エクスポート）が別ターンの値を読む。累積する `covered_aspects` と、置き換わる `turn_analysis` の違いに注意
- state フィールドの追加は `NotRequired` にし、読む側は `.get()` で欠損許容する（旧チェックポイントにキーが無い）。トポロジーが変わらないなら `GRAPH_VERSION` は上げない（上げると進行中セッションが全て再開不可になる。ただしフィールドの削除・改名は例外 — 「注意事項」節参照）
- **`learning_dialogue` は `intake_complete` キーの「有無」で3経路に振り分けるルーター**: キー欠損 = デプロイ前に始まった旧セッション（旧経路 `prepare_turn`/`respond` をそのまま実行）、`False` = 聞き取り中（`graph/nodes/_intake.py`）、`True` + `depth_map` あり = 地図駆動（`_map_dialogue.py`）、`True` + `depth_map` なし = 地図生成に失敗した旧経路フォールバック。値ではなく**有無**で旧セッションを見分けるため、`learning_start` は新規セッションで必ず `intake_complete=False` を書く（省くと新規セッションが旧経路へ落ちる）。`evals/eval.py` の regression が旧 capture を再生できるのも、`to_state` がこのキーを持たないから。聞き取りの完了ターンで地図生成が失敗すると `handle_intake_turn` は `messages` キーを含まない dict を返し、ルーターが旧経路で応答を作る（`_intake.py` から `learning_dialogue.py` を import すると循環になるため）。`evals/tools/capture.py` は `intake_complete` を持つセッション（新規セッションは全て）を capture 対象外にする。旧形式のレコードとして書くと regression が旧経路で再生してしまうため
- **`should_generate_note` は学習系の全ノード（`respond` / `respond_map` / 聞き取りの `base_updates`）で常に `False` を返す**: 学習セッションはユーザーの明示的な終了操作で完了し、終了スイッチは `api/websocket/chat.py` の `_handle_end_session` が外部から立てる。対話ノードから立てると `MIN_TURNS_BEFORE_NOTE` の判定経路に入ってしまう

### API エンドポイント

| Method | Path | 用途 |
|--------|------|------|
| GET | `/api/health` | ヘルスチェック |
| GET/PATCH | `/api/notes` | ノート取得・更新 |
| GET | `/api/feedbacks` | フィードバック取得 |
| GET | `/api/review-schedules` | 復習スケジュール |
| GET | `/api/dialogue-sessions` | セッション一覧 |
| WS | `/ws/chat` | チャット WebSocket |

### データアクセスパターン

- リポジトリパターン（`repositories/`）: SQL を直接記述、asyncpg で実行
- 依存性注入: `CurrentUser`（JWT 検証済みユーザー ID）と `DB`（コネクション）を `Depends()` で注入
- ORM 不使用、`asyncpg.Record` を直接扱う
- リポジトリ関数の接続引数は `core.database.DBConnection`（`Connection | PoolConnectionProxy`）を使う。`pool.acquire()` が返すのは `Connection` の非サブクラスである `PoolConnectionProxy` のため、両方を受け取れる必要がある（`Pool` を直接渡さず、必ず `acquire()` してから渡す）

### 画像添付（マルチモーダル）

- 対話の `user_message` に画像（JPEG/PNG/WebP・最大4枚・各5MB）を添付できる。クライアントは送信前に長辺2048pxへ縮小し base64 で送る（`client/lib/image.ts`）
- バイナリは `storage/`（dev: ローカルFS、本番: S3 は #128）に保存し、参照メタは `dialogue_message_images` テーブルに持つ。state（チェックポイント）には base64 を載せず storage_key 参照のみ保持し、LLM 呼び出し直前にストレージから読んで base64 data URL を組む（`graph/multimodal.py`）
- LLM へは最新ユーザーメッセージの画像のみ `image_url`（detail=high）ブロックで渡す（会話履歴はプロンプト本文に文字列化されるため）。ノート/フィードバック生成には画像を渡さない
- 履歴の画像は `GET /api/dialogue-sessions/{id}/images/{image_id}` で配信（Bearer 認証必須のためフロントは `fetchImageObjectURL()` で取得）
- 環境変数: `STORAGE_BACKEND`（既定 `local`）・`LOCAL_STORAGE_DIR`（既定 `storage_data`）
- 音声・動画は対象外（音声は #41）

### Langfuse トレース

- 送出は `observability/langfuse_tracing.py` に閉じている。クライアントは `main.py` の lifespan で `init_tracing()` / `shutdown_tracing()`（後者を省くと終了間際のトレースがバッチ送出されずに落ちる）
- 粒度は **1ターン＝1 trace・1対話セッション＝1 Langfuse session**。グラフは `interrupt_before` で毎ターン中断するため、実行の切れ目がそのままターンの境界になる
- グラフ実行は `traced_graph_run()` で自前の root span に包む。LangGraph の実行をそのまま root にすると trace の入出力が `LearningState` 丸ごと（かつ再開ターンでは入力 `None`）になり、一覧・評価器から読めないため。root span にはユーザー発話と応答だけを載せる
- `CallbackHandler` は root span が active な間に生成する必要がある（生成時点の trace context を引き継ぐため）。`build_graph_config()` が返す config に callbacks は入っておらず、`traced_graph_run()` が実行時に足す
- trace 名（`respond-to-user` 等）はダッシュボード・評価器の参照キーになるため、ID やターン番号を混ぜない。変更は破壊的変更として扱う
- `aget_state` / `aupdate_state` はノードを実行しないので callbacks を付けない（付けると中身のない trace が量産される）
- 環境変数: `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`（未設定なら送出は自動的に無効）・`LANGFUSE_BASE_URL`・`LANGFUSE_TRACING_ENVIRONMENT`（既定 `development`）
- **LLM 観測は Langfuse に一本化している**（自前実装の DB テーブル `run_traces` と `measured_node` / `measured_ainvoke` は廃止）。ノードのレイテンシもトークン数も Langfuse 側にしか無いので、集計・eval のデータ源は Langfuse API を使う
- ノードが LLM を複数回呼ぶ場合（`generate_note` は3回、`update_note_and_feedback` は4回、`learning_dialogue` は旧経路・地図駆動とも dialogue intent 時のみ事前分析分を含め2回、聞き取りは `extract-intake` 分を含め2回、聞き取りの完了ターンは `generate-depth-map` と `map-turn-analysis` 分を含め最大4回）だけ `config={"run_name": "..."}` で呼び出しを識別する（`generate-note-content` / `estimate-category` / `analyze-dialogue` / `turn-analysis` / `map-turn-analysis` / `extract-intake` / `generate-depth-map` など）。1ノード1呼び出しの対話ノードには付けない（ノードスパン名と二重になる）
- **プロンプト本文の同一性は `prompt_version` ではなく `prompt_fingerprint`（質問生成 + 事前分析プロンプトの内容ハッシュ）で判定する**。`prompt_version` は手で維持するラベルなので、上げ忘れ・振り直しで本文との対応が崩れる。実際に 2026-08-04 以前の trace は `generate_question@v1` と `@v2` の 2 ラベルに割れているが本文は同一で、版ラベルで絞ると取りこぼす（`@v2` を欠番にして現行を `@v3` にしたのはこのため）
- **`config={"metadata": ...}` を渡しても trace 属性（session / user / tags）は落ちない**が、それは冗長性に支えられている。`ensure_config` は contextvar 側の metadata を**マージせず置換**するため、`build_graph_config()` が入れている `langfuse_*` キーはその observation から消える。それでも属性が付くのは `traced_graph_run()` が `propagate_attributes()` で OTEL レベルにも同じ属性を伝播しているため（切り分け実験で両経路が独立に機能することを確認済み）。**`traced_graph_run` の外でグラフや LLM を実行しつつ metadata を上書きすると、session グルーピングが静かに壊れる**

### フロントエンドのパターン

- `use-chat-websocket.ts`: 接続ライフサイクル・メッセージ型振り分けを一元管理
- `fetchAPI()`: 全 REST 呼び出しはここを経由（JWT ヘッダー付与、エラーハンドリング）
- `NavbarSlotContext`: レイアウト内でナビバーに動的コンテンツを挿入するポータルパターン
- チャットのメッセージ本文は `Markdown` の `variant="chat"`（`remark-breaks` で単一改行を保持・`rehype-highlight` でコードをハイライト）で描画。ストリーミング中は `closeOpenCodeFence()` で未閉じフェンスを補ってから渡す（`notes`/`review` の `default`/`article` variant とは別系統）
- コピーは各メッセージ単位（`MessageCopyButton` が `msg.content` 全文をコピー）。未フェンスの貼り付けコードでも全文コピーできるよう、コードブロック単位ではなくメッセージ単位にしている

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

---

## 注意事項（ハマりポイント）

> **このセクションの育て方**: 実装中に、コードを読むだけでは分からない制約・ライブラリの癖・型の落とし穴（例: 下記の asyncpg Pool/Connection 型不一致）に直面し、それを考慮して実装・修正したときは、その教訓をここへ追記することを提案する。判断基準は「コードから読み取れることは書かない。『なぜ』『制約』だけ書く」。これにより、以降の実装が同じ問題を最初から考慮できるようにする。

- **マイグレーション順序**: `alembic upgrade head` の前に `client/better-auth_migrations/*.sql` を適用すること（外部キー制約あり）
- **BetterAuth スキーマは静的SQLで `auth.ts` と自動同期しない**: `client/better-auth_migrations/*.sql` は生成時点のスナップショット。`client/lib/auth.ts` のプラグイン（例: `jwt()` は `jwks` テーブルを要求）を追加・変更したら `npx @better-auth/cli generate --config lib/auth.ts` で再生成してコミットすること。漏れると新環境で `relation "jwks"/"user" does not exist` になる（過去に `jwks` 欠落で認証が落ちた）
- **`better-auth_migrations/` は常にスナップショット1ファイルのみに保つ**: `generate` が出すのは差分ではなくフルスキーマで、実行するたび新しいタイムスタンプ名のファイルが増える。再生成したら古いファイルを削除すること。複数残すと `make setup` のループが古い方を先に適用し、新しい方は全文 `already exists` で失敗する（`-v ON_ERROR_STOP=1` を入れる前は psql が exit 0 を返すため、古いスキーマのまま成功したように見えていた）。`migrate` サブコマンドは `client/.env.local` の `DATABASE_URL` へ直接 DDL を打つので、適用先の確認なしに使わない
- **スタック状セッション**: サーバー起動時に `reset_stuck_generations()` が自動実行される（`main.py` の `lifespan` 参照）
- **LangGraph 永続化**: チェックポイントは DB に保存されるため、ローカル開発中にスキーマ変更するとチェックポイントとの不整合が起きる場合がある
- **DB テーブル**: `notes`, `dialogue_sessions`, `dialogue_messages`, `feedbacks`, `review_schedules` が主要テーブル。BetterAuth テーブル（`user`, `account`, `session` 等）も同一 DB に存在し、外部キー制約によるカスケード削除あり
- **CORS**: `CORS_ORIGINS` 環境変数でカンマ区切りで複数指定可能（デフォルト `http://localhost:3000`）
- **ストリーミング対象ノード内の内部 LLM 呼び出しには `INTERNAL_LLM_TAG` を付ける**: WebSocket の `_stream_ai_response` は `stream_mode="messages"` を「ノード名が `_STREAMING_NODES` に含まれるか」だけでフィルタするため、対象ノード（例: `learning_dialogue`）の中で行う structured output 等の追加 LLM 呼び出しの出力（生 JSON）もそのままクライアントへ流れてしまう。内部呼び出しの runnable に `.with_config(tags=[INTERNAL_LLM_TAG])`（`graph/llm.py`）を付与すること。chat.py 側がこのタグ付きチャンクを除外する
- **「今日」の暦日判定はユーザーTZで行う**: 復習スケジュールの時刻列は `TIMESTAMPTZ`（UTC 保持）。「今日復習を完了した件数」のような暦日集計を `last_reviewed_at::date = CURRENT_DATE` でやるとサーバーの稼働 TZ 次第で日付境界がずれる。`(last_reviewed_at AT TIME ZONE $tz)::date = (NOW() AT TIME ZONE $tz)::date` のようにユーザーTZ（`REVIEW_TIMEZONE`、既定 `Asia/Tokyo`）へ変換してから比較する。なお「期限到来済みか」の判定（`next_review_at <= NOW()`）は瞬間の前後比較なので TZ 非依存で問題ない。暦日に丸める集計だけが TZ 依存。
- **復習完了はダッシュボードに残さず消す**: ダッシュボード（`GET /api/review-schedules`）は `next_review_at <= NOW()` かつ `status IN ('pending','overdue')` の未到来分だけを返す。実際の復習完了（review セッションの `update_note_and_feedback` → `_advance_review_schedule`）で `next_review_at` が将来へ進むと自動的に一覧から消える。フロントで「開いた＝復習済み」のような疑似状態を持って表示を残さない（次回到来まで非表示が正）。当日の進捗バーに必要な「当日完了件数」は一覧から消えるため `completed_today` として別途集計して返している
- **golden の deterministic assertion は `check_fingerprint`（`evals/checks.py` の実装の内容ハッシュ）を持たせる**: `check:` の名前だけでは golden から実装を辿れず、検出フレーズや判定ロジックを変えても record は無変更で通る。ずれたまま採点すると `human_verdicts` との不一致が judge の誤りとして現れ、**judge のせいでない failure を judge のせいだと誤診する**。値が動いたら criterion を読み直してから転記すること（実装が変わった記録であって、criterion がまだ実装を正しく説明しているかは人間しか判断できない）
- **`LearningState` のキー削除・改名は `GRAPH_VERSION` を上げる**（トポロジー不変でも例外）: `should_interrupt()`（`_algo.py`）はチェックポイントに永続化された `channel_versions` を丸ごと参照するが、`versions_seen[INTERRUPT]` の更新（`_loop.py`）は現在のグラフが宣言しているチャンネルにしか及ばない。宣言から消えたキーの version は永遠に「済」にならず、そのキーに値を持つ既存スレッドは `learning_dialogue` / `review_dialogue` の直前で毎ターン再中断し続け、進行不能になる
- **再開時に「応答が返らないまま残ったユーザーメッセージ」を巻き戻す**: 応答生成の途中で切断すると、DB と state にユーザーメッセージだけが残る。放置するとユーザーは同じ内容を再送するしかなく、履歴に同一発言が二重に残る（実セッションで発生）。`_handle_resume_session` の `_rollback_unanswered_turn()` が state（`RemoveMessage`）と DB の両方から取り除き、`pending_message_rolled_back` でクライアントの入力欄へ戻す。対話ノードは走っていないので `turn_count` は触らない。state への反映前に落ちた場合は DB 側にだけ残るので、そちらも同じ関数が拾う
- **対話ノードは `prepare_turn`（事前分析）と `respond`（応答生成）に分かれている**: eval が保存済みの決定を注入して応答生成だけ再実行できるようにするため（`--replay-mode pinned`）。分析の揺れとプロンプト改訂の効果を切り分けられなくなるので、この分割を戻さないこと。旧経路の `learning_dialogue` は両方を順に呼ぶだけ（地図駆動にも同じ `prepare_map_turn` / `respond_map` の分割がある）
- **eval の judge カスケードは screen の fail だけを confirm に回す**: エスカレーション条件（`should_escalate`）は `holds` ではなく polarity 適用後の verdict で判定する。screen（既定 Haiku）の FN（欠陥を pass と言う誤り）は confirm（既定 Opus）に届かないため最終判定に残る。scoring の校正ゲートは screen 単体の TPR も出すので、そこを見て「カスケードで救えない」誤りが無いか確認すること
