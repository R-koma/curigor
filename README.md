# Curigor

> 「人に教えることで学ぶ（プロテジェ効果）」を LLM との対話でシステム化した、長期記憶定着のための学習アプリケーション。

[![CI](https://github.com/R-koma/curigor/actions/workflows/ci.yml/badge.svg)](https://github.com/R-koma/curigor/actions/workflows/ci.yml)
![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-LangGraph-009688?logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql)

---

## 目次

- [概要](#概要)
- [主な特徴](#主な特徴)
- [アーキテクチャ](#アーキテクチャ)
- [技術スタック](#技術スタック)
- [LangGraph フロー](#langgraph-フロー)
- [セットアップ](#セットアップ)
- [開発](#開発)
- [テスト](#テスト)
- [ディレクトリ構造](#ディレクトリ構造)
- [ドキュメント](#ドキュメント)

---

## 概要

インプットした知識を「自分の言葉で説明する（アウトプットする）」機会の不足によって、記憶が揮発してしまう課題を解決するための学習定着アプリケーションです。

「プロテジェ効果（人に教えることで学ぶ）」を LLM との対話によってシステム化しています。ユーザーが学習内容を入力すると、LLM が的確な深掘り質問を投げかけます。それに「自分の頭で思い出して答える」だけで、バラバラだった知識が意味のある塊として整理され、最小のインプットで最大の長期記憶定着（アウトカム）を実現します。

## 主な特徴

- **LLM との深掘り対話**: LLM エージェントからの質問に答えることで、記憶の引き出しを強力にサポート
- **ノート＆フィードバック自動生成**: 対話セッション終了時に、要約と重要な概念を自動でノート化して保存
- **忘却曲線に基づく復習**: エビングハウスの忘却曲線を利用し、最適なタイミングで復習をスケジュール

---

## アーキテクチャ

```mermaid
graph TB
    subgraph Client["client (Next.js 16)"]
        Auth["BetterAuth\n(OAuth / セッション管理)"]
        TextChat["チャット UI\n(use-chat-websocket)"]
        RSC["復習ダッシュボード / ノート一覧\n(React Server Components)"]
    end

    subgraph Server["server (FastAPI)"]
        JWTMiddleware["JWT 検証\n(JWKS 公開鍵による Bearer 認証)"]
        WSChat["/ws/chat\nSession → LangGraph"]
        REST["REST API\n(ノート / 復習スケジュール)"]
    end

    subgraph DB["PostgreSQL 17"]
        Users["ユーザー (BetterAuth 管理)"]
        Notes["ノート / フィードバック"]
        Review["復習スケジュール"]
        Checkpoint["LangGraph チェックポイント"]
    end

    TextChat <-->|WebSocket| WSChat
    RSC <-->|REST| REST
    Auth -.->|セッション Cookie| JWTMiddleware
    Server --> DB
```

## 技術スタック

### フロントエンド

| カテゴリ | 技術 | 用途 |
|----------|------|------|
| フレームワーク | Next.js 16 (App Router) + React 19 | SSR/RSC 対応のフルスタックフレームワーク |
| 言語 | TypeScript (strict) | 型安全なフロントエンド開発 |
| 認証 | BetterAuth | OAuth / セッション管理 |
| WebSocket | カスタム Hook (`use-chat-websocket`) | サーバーとの双方向リアルタイム通信 |
| UI | shadcn/ui + Tailwind CSS | コンポーネントライブラリ |
| Markdown | react-markdown | LLM 応答のレンダリング |

### バックエンド

| カテゴリ | 技術 | 用途 |
|----------|------|------|
| 言語 | Python 3.13 | - |
| Web フレームワーク | FastAPI + Uvicorn | WebSocket / REST エンドポイント |
| LLM オーケストレーション | LangGraph + LangChain | 学習フローの状態管理・ルーティング |
| LLM | OpenAI `gpt-4.1-nano` | 対話・ノート生成・フィードバック |
| 認証検証 | PyJWT + JWKS | BetterAuth 発行 JWT の公開鍵検証 |
| パッケージ管理 | uv | 依存関係管理 |

### データベース

| カテゴリ | 技術 | 用途 |
|----------|------|------|
| RDBMS | PostgreSQL 17 + pgvector | 全データの永続化・ノートの埋め込みの近傍検索 |
| データアクセス | asyncpg + 生 SQL | SQL ファーストアプローチ（ORM 不使用）|
| チェックポイント | langgraph-checkpoint-postgres | LangGraph フロー状態の永続化 |
| マイグレーション | Alembic | スキーマバージョン管理 |

## LangGraph フロー

```
START
  └─► learning_start
        └─► learning_dialogue ──（対話継続）──► learning_dialogue（最大 3 ターン）
                                └─（LEARNING_END）─► generate_note ─► generate_feedback ─► END
                                └─（review セッション）────────────► generate_feedback ─► END
```

- **learning_start**: トピックを受け取り、最初の深掘り質問を生成
- **learning_dialogue**: 深掘り対話を継続。`should_generate_note` が true になると次フェーズへ
- **generate_note**: 対話履歴全体から Structured Output でノートを自動生成（review セッションはスキップ）
- **generate_feedback**: ノートを評価し、理解度（high/medium/low）・良かった点・改善点を返却

> 技術選定の背景・比較検討・トレードオフは [docs/adr/](docs/adr/) を参照。

---

## セットアップ

### 前提条件

- Docker / Docker Compose
- Node.js 24+
- Python 3.13+
- [uv](https://docs.astral.sh/uv/)

### 初回セットアップ

```bash
# 1. リポジトリをクローン
git clone <repo-url>
cd curigor

# 2. 環境変数を設定
cp .env.example .env                      # POSTGRES_PASSWORD 等を記入（未設定だと docker compose が起動しない）
cp server/.env.example server/.env        # OPENAI_API_KEY 等を記入
cp client/.env.example  client/.env.local # BETTER_AUTH_SECRET 等を記入

# 3. 依存関係のインストール・DB 構築・マイグレーションを一括実行
make setup
```

`make setup` は server の `uv sync`、開発用 DB の起動、BetterAuth テーブル作成、Alembic マイグレーション、pre-commit フックの導入、client の `npm install` までを実行します。

### 開発サーバーの起動

```bash
make dev-db      # DB（初回のみ or 停止後）
make dev-server  # バックエンド（別ターミナル）
make dev-client  # フロントエンド（別ターミナル）
```

| 用途 | URL |
|------|-----|
| フロントエンド | http://localhost:3000 |
| API ドキュメント (Swagger) | http://localhost:8000/docs |
| ヘルスチェック | http://localhost:8000/api/health |

---

## 開発

### よく使うコマンド

| 目的 | コマンド |
|------|---------|
| Lint + フォーマット (server) | `cd server && uv run ruff check . --fix && uv run ruff format .` |
| 型チェック (server, strict) | `cd server && uv run mypy .` |
| Lint + 型チェック (client) | `cd client && npm run lint && npx tsc --noEmit` |
| マイグレーション生成 | `cd server && uv run alembic revision --autogenerate -m "description"` |
| マイグレーション適用 | `cd server && uv run alembic upgrade head` |
| ADR 雛形生成 | `make adr name=your-title` |

### コード規約

- **Python**: Ruff + mypy strict（行長 119 / Python 3.13 / ルール E,W,F,I,B,UP）
- **TypeScript**: ESLint + Prettier（strict モード）
- **pre-commit**: コミット時に ruff（server）/ mypy（server）/ prettier（client）が自動実行（`uv run pre-commit install`）

> **マイグレーション順序の注意**: `alembic upgrade head` の前に `client/better-auth_migrations/*.sql` を適用する必要があります（外部キー制約）。`make setup` はこの順序を自動で行います。

> **BetterAuth スキーマの再生成**: `client/better-auth_migrations/*.sql` は静的スナップショットで、`client/lib/auth.ts` のプラグイン構成とは自動同期しません。プラグインを追加・変更したとき（例: `jwt()` は `jwks` テーブルを要求）は再生成してコミットしてください。漏れると新環境のセットアップ時に `relation "jwks"/"user" does not exist` で認証が失敗します。

クライアント側のマイグレーションコマンドは 2 つあり、役割が異なります。

| コマンド | 動作 |
|----------|------|
| `cd client && npx @better-auth/cli generate --config lib/auth.ts` | 現在のプラグイン構成に対応する**フルスキーマ SQL を新しいファイル名で出力**する。DB には一切触れない |
| `cd client && npx @better-auth/cli migrate --config lib/auth.ts` | `client/.env.local` の `DATABASE_URL` が指す DB へ**直接 DDL を適用**する。ファイルは残らない |

`generate` は認証モジュールの `import "server-only"` で読み込みに失敗するので、実行の間だけその行を外すか差し替えてください。

リポジトリの正規手順は `generate` で SQL を出してコミットし、DB への適用は `make setup`（psql 経由）に任せる方です。`migrate` は接続先が `client/.env.local` 依存なので、意図しない DB へ適用しないか確認してから使ってください。

> **スナップショットは常に 1 ファイルだけ**: `generate` が出力するのは差分ではなくフルスキーマです。再生成したら**古いファイルを削除**して、`client/better-auth_migrations/` には最新の 1 ファイルのみを置いてください。複数残すと `make setup` が古い方を先に適用し、新しい方は全文 `already exists` で失敗します。

### トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| `relation "user" does not exist`（`alembic upgrade head` 時） | BetterAuth の認証SQL未適用 | `client/better-auth_migrations/*.sql` を先に適用（`make setup` が自動実行） |
| `relation "jwks" does not exist` など、認証・JWT 発行時のスキーマ不整合 | コミット済みスナップショットが `client/lib/auth.ts` のプラグイン構成より古い | `cd client && npx @better-auth/cli generate --config lib/auth.ts` で再生成し、古いスナップショットを削除して 1 ファイルにしてコミット。開発 DB は `docker compose down -v` → `make setup` で作り直す |
| `role "..." does not exist`（psql/接続時） | `.env` の `POSTGRES_USER` と接続先ユーザーの不一致 | DBコンテナの実値（`docker compose exec db printenv POSTGRES_USER`）に合わせる |
| `relation "user" already exists`（`make setup` 時） | 認証SQLのスナップショットが複数ある、または適用済みの DB に再実行した | `client/better-auth_migrations/` を最新 1 ファイルに整理する。作り直す場合は `docker compose down -v` でボリュームごと削除してから `make setup` |

---

## テスト

| 種別 | 場所 | フレームワーク | カバレッジ目標 |
|------|------|--------------|--------------|
| バックエンド unit | `server/tests/unit/` | pytest | 60% |
| バックエンド integration | `server/tests/integration/` | pytest | - |
| フロントエンド | `client/__tests__/` | Vitest | - |

```bash
make test-db                                   # テスト用 DB 起動（初回のみ）
cd server && uv run pytest --cov=. --cov-report=term
cd client && npm run test
```

- DB を使うテストは実 PostgreSQL に接続します（**モック禁止**）
- `asyncio_mode = "auto"` のため `@pytest.mark.asyncio` は不要

### CI（GitHub Actions）

`main` への push / PR で以下が必須通過です。`prompt-change` ラベル付き PR では LLM プロンプトの eval（smoke / regression）も追加実行されます。

`server-lint` ・ `server-typecheck` ・ `server-test` ・ `client-lint` ・ `client-test` ・ `secret-scan`（Gitleaks）

---

## ディレクトリ構造

```
.
├── client/                    # Next.js フロントエンド
│   ├── app/
│   │   ├── (auth)/            # sign-in, sign-up
│   │   └── (main)/            # dashboard, learn, notes, review/[noteId]
│   ├── components/
│   │   ├── chat/              # チャット UI
│   │   ├── layout/            # sidebar, navbar
│   │   └── ui/                # shadcn/ui コンポーネント
│   ├── hooks/
│   │   └── use-chat-websocket.ts  # WebSocket ライフサイクル管理
│   ├── lib/
│   │   ├── api.ts             # fetchAPI()（JWT 自動付与）
│   │   └── auth.ts / auth-client.ts
│   └── __tests__/             # Vitest テスト
│
├── server/                    # FastAPI バックエンド
│   ├── main.py                # エントリーポイント・lifespan
│   ├── api/
│   │   ├── routes/            # REST: note, feedback, review_schedule, dialogue_session
│   │   ├── websocket/chat.py  # WebSocket (/ws/chat)
│   │   └── dependencies.py    # CurrentUser, DB
│   ├── core/                  # auth, config, database
│   ├── graph/                 # LangGraph: builder, state, nodes, prompts
│   ├── repositories/          # SQL-first データアクセス
│   ├── schemas/               # Pydantic モデル
│   ├── services/              # review_scheduler など
│   └── tests/unit/ & integration/
│
├── docs/adr/                  # アーキテクチャ決定記録
├── docker-compose.yml
└── Makefile
```

---

## ドキュメント

- [CLAUDE.md](CLAUDE.md) — 開発者・AI エージェント向けのプロジェクト詳細ガイド
- [docs/adr/](docs/adr/) — アーキテクチャ決定記録（技術選定の背景）
</content>
</invoke>
