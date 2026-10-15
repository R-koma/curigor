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
```

eval・capture・annotate のコマンドと jsonl の規約は `.claude/rules/server/evals.md`。

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
│   ├── nodes/                 # learning_start, learning_dialogue, generate_note, generate_feedback, review_start, review_dialogue, update_note_and_feedback, synthesis, explore_start, explore_dialogue, generate_study_memo
│   └── prompts/               # タスク別プロンプト（intake, depth_map, map_question, analysis, note, feedback, review, question, explore）
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
├── evals/                     # eval.py（scoring / regression の CLI。部品は dataset・replay・judge・runner・metrics・report・emit・retry）・checks.py・golden_yaml.py・taxonomy.py・tools/capture.py + datasets/ + README.md（golden の規約・judge の決定）・pending/ + verify.py（eval の確認待ちとレポートとの照合）・feedback.py + tools/capture_feedback.py（フィードバックの理解度）・review_end.py（復習の終了判定）・transcription.py + tools/record_audio/（文字起こしの精度）
└── tests/
    ├── unit/                  # pytest + 実 DB（モック禁止）
    └── integration/

client/
├── app/
│   ├── (auth)/                # sign-in, sign-up
│   ├── (main)/                # dashboard, learn, notes/[id], review/[noteId], study-memos/[id]
│   └── api/                   # Next.js Route Handlers（auth/[...all], upload-avatar）
├── context/                   # navbar-slot-context.tsx（ナビバー差し込み）
├── components/
│   ├── chat/                  # chat-input など
│   ├── layout/                # sidebar, navbar, main-layout-client
│   ├── notes/
│   ├── study-memos/
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
  ├─ "synthesis" → synthesis_start → synthesis_dialogue（ループ）→ finish_synthesis → END
  └─ "explore"   → explore_start   → explore_dialogue（ループ）  → generate_study_memo → END
```

ノード・state・経路の規則は `.claude/rules/server/graph.md`。

### API エンドポイント

| Method | Path | 用途 |
|--------|------|------|
| GET | `/api/health` | ヘルスチェック |
| GET/PATCH | `/api/notes` | ノート取得・更新 |
| GET | `/api/notes/{id}/feedbacks` | フィードバック取得（評価の履歴） |
| GET | `/api/review-schedules` | 復習スケジュール |
| GET | `/api/dialogue-sessions` | セッション一覧 |
| GET/POST/PATCH/DELETE | `/api/collections` | まとめノート（ノートの束ね先） |
| PUT/DELETE | `/api/notes/{id}/collection`, `/collection-suggestion` | ノートをまとめノートに入れる・外す・候補を断る |
| GET/PUT | `/api/notes/{id}/links`, `/links/{link_id}` | 別のまとめノートのノートとのつながり（候補・採用済み）の取得と採否 |
| GET | `/api/study-memos`, `/api/study-memos/{id}` | 学習メモ（インプットセッションの観点・用語集・疑問と回答。一覧は `handed_over` を持つ） |
| GET/POST | `/api/collections/{id}/synthesis` | まとめの下書きの取得・生成（同期） |
| POST | `/api/transcriptions` | 音声の文字起こし（multipart。`audio/wav` の発話区間を含む） |
| POST | `/api/speech` | 応答の読み上げ（JSON → PCM のストリーム） |
| GET/PUT/DELETE | `/api/hints/dismissals`, `/{hint_id}` | 閉じた使い方のヒントの取得・記録・全消去 |
| DELETE | `/api/account/data` | アカウントの削除の前に、チェックポイント・添付画像・Langfuse の trace を消す（BetterAuth の `beforeDelete` から呼ぶ） |
| WS | `/ws/chat` | チャット WebSocket |

### データアクセスパターン

- リポジトリパターン（`repositories/`）: SQL を直接記述、asyncpg で実行
- 依存性注入: `CurrentUser`（JWT 検証済みユーザー ID）と `DB`（コネクション）を `Depends()` で注入
- ORM 不使用、`asyncpg.Record` を直接扱う
- リポジトリ関数の接続引数は `core.database.DBConnection`（`Connection | PoolConnectionProxy`）を使う。`pool.acquire()` が返すのは `Connection` の非サブクラスである `PoolConnectionProxy` のため、両方を受け取れる必要がある（`Pool` を直接渡さず、必ず `acquire()` してから渡す）

認証・画像添付・音声・ノートの埋め込み・Langfuse は `.claude/rules/` の各ファイル（下の一覧）。

### フロントエンドのパターン

- `fetchAPI()`: 全 REST 呼び出しはここを経由（JWT ヘッダー付与、エラーハンドリング）
- `NavbarSlotContext`: レイアウト内でナビバーに動的コンテンツを挿入するポータルパターン
- チャット画面・UI の規約は `.claude/rules/client/session.md`・`client/ui.md`

---

## 機能別の規約（`.claude/rules/`）

機能ごとの設計・制約・ハマりポイントは `.claude/rules/` に分けてある。各ファイルの `paths` に一致するファイルを Read / Edit すると自動で読み込まれる。触る前に関係すると分かっているときは先に読むこと。ここに書いていない横断の規約だけがこのファイルに残る。

| ファイル | 読み込まれる場面 | 内容 |
| --- | --- | --- |
| `server/graph.md` | `server/graph/**`・`server/api/websocket/**` | LangGraph のノード・state・経路の分岐・聞き取り・トピック訂正・セッション終了、`GRAPH_VERSION`・`INTERNAL_LLM_TAG`・巻き戻し |
| `server/evals.md` | `server/evals/**` | eval のコマンドと jsonl の規約、golden の `check_fingerprint`、judge カスケード |
| `server/langfuse.md` | `server/observability/**`・`graph/llm.py`・`graph/nodes/**` | トレースの粒度、`run_name`、モデルの選択、`prompt_fingerprint` |
| `server/review.md` | 復習の services / routes / nodes、`client/components/review/**`・`dashboard/**` | 暦日の TZ、`review_count`、期限前の復習、重点の観点 |
| `server/notes.md` | ノート・まとめノート・埋め込みの services / repositories / routes / prompts、`client/components/notes/**` | 埋め込みと候補、観点マップの ID、ノート本文の節、フィードバックの履歴 |
| `voice.md` | `speech` / `transcription` の routes と実装、`client/lib` の音声系、`use-voice-*`、`voice-*.tsx` | STT・VAD・声で話す・読み上げ |
| `auth.md` | `client/lib/auth*`・`dev-auth.ts`・`email/**`・`app/(auth)/**`・`better-auth_migrations/**`・`server/core/auth.py` | メール OTP、開発用の自動ログイン、BetterAuth のスナップショット |
| `images.md` | `server/storage/**`・`graph/multimodal.py`・`client/lib/image.ts` | 画像添付 |
| `client/session.md` | `use-chat-websocket.ts`・`app/(main)/learn|review/**`・`components/chat/**` | 再接続、進捗表示、トピック訂正・編集の UI、終了ボタン |
| `client/ui.md` | `client/app/**`・`client/components/**`・`client/__tests__/**` | デザイントークン、ツールチップ、スマホ幅、ヒント、アカウント欄、Node 25 の `localStorage` |

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
- `client-lint`: eslint + `tsc --noEmit` + `next build`
- `client-test`: vitest
- `secret-scan`: Gitleaks

依存の脆弱性と更新は Dependabot（`.github/dependabot.yml`。npm・uv・GitHub Actions・Dockerfile を毎週）。alerts と security updates はリポジトリの設定で有効にしてある。CI に `npm audit`・`pip-audit` は入れない（alerts と重なり、新しい CVE が出ると関係のない PR まで落ちる）。Node のメジャーは Dependabot から外してあり、`.nvmrc`・`engines`・CI・Dockerfile を揃えて手で上げる

Dependabot のブランチは Vercel のプレビューを作らない（`client/vercel.json` の `git.deploymentEnabled`）。Hobby のデプロイ回数（1 日 100）と関数のストレージをまとめて使い切るため。ビルドが通るかは CI の `next build` で確かめる

`codeql.yml`（actions・python・javascript-typescript、`security-extended`）は PR・main への push・週 1 回で走り、結果は Security タブに出る。検出で PR は止めない（誤検知の量を見て必須にするか決める）

---

## コード規約

### コメント（言語共通）

**既定は「書かない」**。残してよいのは、**コードからも周辺ファイルからも復元できない事実**だけ ——
外部仕様・ライブラリの癖・ブラウザやフォーマットの挙動・ファイルをまたぐ値の一致制約。

**「なぜ」を書いてあれば残る、ではない。** 以下は理由が書かれていても削除対象:

| 削除対象 | 例 |
| --- | --- |
| コードの言い換え | `assert record is not None  # INSERT ... RETURNING は必ず1行返す`、`if TAG in tags: continue` の上に付けた「内部呼び出しの出力を流さない」 |
| **CLAUDE.md・`.claude/rules/` に書いてある知識の再掲** | `GRAPH_VERSION` の用途、`turn_analysis` に `None` を明示する理由、`INTERNAL_LLM_TAG`、`REVIEW_TIMEZONE` の暦日判定、`completed_today` の存在理由、Langfuse の `CallbackHandler` を root span 内で生成する理由 |
| 定数・環境変数への説明 | `core/config.py` の各変数（名前と既定値で足りる） |
| テスト内の手続き説明 | テスト名・docstring・アサーションと重複する行、`# 現在時刻より過去` のような値の注釈 |
| 型エイリアスの背景解説 | 他の型との対応表など、使う側が知らなくても正しく書けるもの |
| 直後の分岐・例外メッセージで自明な意図 | `raise ValueError("Invalid storage key")` の上の「パストラバーサルを防ぐ」 |

**プロジェクト規約の正本は CLAUDE.md と `.claude/rules/`**。コード側に複製しないこと（二重管理になり、CLAUDE.md を直しても
コメントが古いまま残る）。逆に、コードから読み取れない制約に気づいたらコメントではなくこの CLAUDE.md へ書く。

残す場合も**最短で書く**。修飾語を削って 1〜2 行に収める。

- 残す例: `# 保存 mime は実体と一致する保証がないため、ブラウザの MIME スニッフィングを抑止する（多層防御）`（ブラウザ挙動）/
  `core/database.py` の `DBConnection` の型注記（asyncpg の癖）/ `# WebP は RIFF コンテナ: "RIFF"<4byte size>"WEBP"`（フォーマット仕様）/
  「値はプロンプト本文（`graph/prompts/review.py`）の指示と一致させる」（ファイルをまたぐ制約）
- 判断に迷ったら書かない。コメントで補うより、命名と関数分割でコード自体を読めるようにする。

### Python（Ruff + mypy strict）
- 行長: 119 文字、Python 3.13 ターゲット
- ルール: E, W, F, I, B, UP, S
  - `S101`（assert）は全体で除外。mypy の型の絞り込みに使っており、本番は `-O` で動かさない
  - `S608` は、列名リスト・テーブル名などコードに書いた固定の識別子・定数だけを f-string で SQL に埋め込む箇所に `# noqa: S608` を付ける。外から来る値は必ず `$1` などのプレースホルダで渡す
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

> **このセクションの育て方**: 実装中に、コードを読むだけでは分からない制約・ライブラリの癖・型の落とし穴（例: 下記の asyncpg Pool/Connection 型不一致）に直面し、それを考慮して実装・修正したときは、その教訓を追記することを提案する。置き場は、機能別の規約が `.claude/rules/` にあればそのファイルの「注意事項」、横断のものだけここ。判断基準は「コードから読み取れることは書かない。『なぜ』『制約』だけ書く」。これにより、以降の実装が同じ問題を最初から考慮できるようにする。

- **DB イメージは pgvector 入り**: `CREATE EXTENSION vector` のマイグレーションがあるため、素の `postgres:17` では `alembic upgrade head` が失敗する。既存のローカル DB は `docker compose up -d db db_test` で `pgvector/pgvector:pg17` に作り直す（同じ PostgreSQL 17 なのでボリュームはそのまま使える）。本番（Railway）の Postgres も拡張を入れられることが前提
- **マイグレーション順序**: `alembic upgrade head` の前に `client/better-auth_migrations/*.sql` を適用すること（外部キー制約あり）
- **スタック状セッション**: サーバー起動時に `reset_stuck_generations()` が自動実行される（`main.py` の `lifespan` 参照）
- **DB テーブル**: `notes`, `dialogue_sessions`, `dialogue_messages`, `feedbacks`, `review_schedules` が主要テーブル。BetterAuth テーブル（`user`, `account`, `session` 等）も同一 DB に存在し、外部キー制約によるカスケード削除あり
- **CORS**: `CORS_ORIGINS` 環境変数でカンマ区切りで複数指定可能（デフォルト `http://localhost:3000`）
- **外部 API を長く待つ REST ルートでは `DB` 依存を使わない**: `get_db` はリクエストの間ずっとプール（既定 最大 10）からコネクションを借り続ける。文字起こしのように数十秒かかる呼び出しが数件重なると、他の全エンドポイントと WebSocket が `pool.acquire()` で待たされる。`get_pool()` から必要なクエリの間だけ `acquire()` し、外部呼び出しの前に手放す（`api/routes/transcription.py`）
