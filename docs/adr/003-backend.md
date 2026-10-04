# ADR-0002: バックエンドフレームワークにFastAPIを採用する

## Status

Accepted

## Context

Curigor（LLMを活用した対話型学習支援システム）の本実装にあたり、バックエンドのフレームワークおよびWebSocket接続時の認証方式を選定する必要がある。

### 背景

- PoCではPython 3.13 + FastAPIで実装し、WebSocketによるテキスト/音声チャットの双方向通信、およびLangGraphによる学習フローの状態管理が動作することを検証済み
- PoCではセッション状態とノートデータがインメモリ管理であり、サーバー再起動で全データが消失する課題があった
- ADR-0001にて、フロントエンドにNext.js（App Router）+ TypeScriptを採用し、Better AuthによるOAuth認証をフロントエンド側で完結させる方針が決定済み。バックエンドはJWTによるセッショントークンの検証を担う
- WebSocket通信はNext.jsのサーバーを経由せず、FastAPIに直接接続する構成がADR-0001で前提として記録されている

### 本実装で求められる要件

- WebSocketエンドポイント（テキスト/音声チャットのリアルタイム双方向通信）
- LangGraphとの統合
- JWT検証（Next.jsから発行されたセッショントークンの検証）
- DB接続（ノート、復習スケジュール、ユーザーデータの永続化）
- STT/TTS処理（OpenAI Whisper + gpt-4o-mini-tts）

### 判断軸（優先順位順）

1. **LangGraph/LLMエコシステムとの親和性**: LangGraphの採用が確定しており、これとの統合が最優先
2. **WebSocketのパフォーマンス・安定性**: コア機能がリアルタイムチャットであり、安定したWebSocket処理が必要
3. **開発速度・PoCからの移行コスト**: PoCのコード資産を活かし、迅速に本実装へ移行したい
4. **型安全性・保守性**: 長期的なメンテナンス性

---

## Decision

### 1. バックエンドフレームワーク

**FastAPI（Python）をモノリスとして採用する。**

PoCのスタックを継続し、Go等の他言語によるマルチサービス構成は現段階では導入しない。

### 2. WebSocket認証方式

**方式: HTTPアップグレード時のCookieベース認証を採用する。**

Better AuthのセッションCookieをWebSocketハンドシェイク時に自動送信し、FastAPI側でCookieを検証した上でWebSocket接続を確立する。

---

## Reasons

### バックエンドフレームワーク選定

#### Option A: FastAPI（Python）モノリス ✅ 採用

**メリット:**

- **LangGraph/LLMエコシステムとの親和性**: LangGraph、LangChain、OpenAI SDK等のLLMエコシステムはPythonがファーストクラスサポートであり、最新機能への追従が最も速い。FastAPIの`async/await`とLangGraphの非同期実行は自然に統合できる
- **PoCからの移行コスト最小**: PoCで検証済みのWebSocketエンドポイント、LangGraphフロー、STT/TTS統合のコードをそのまま発展させられる
- **WebSocketの十分なパフォーマンス**: 本アプリのバックエンド処理はほぼ全てI/Oバウンド（LLM APIの応答待ち、DB読み書き）であり、FastAPIの`async/await`で十分に捌ける。CPUバウンドなボトルネックが存在しないため、Goの並行処理性能が活きる場面がない
- **Pydanticとの統合**: Structured Output（LLMの応答をPydanticモデルにパース）がPoCで検証済みであり、API入出力のバリデーションとLLM出力の型安全性を同一のPydanticモデルで統一的に扱える

**デメリット:**

- Pythonの動的型付けに起因する保守性の課題がある
- 将来的にユーザー数が大幅に増加した場合、CPUバウンドな処理が発生すればパフォーマンス上の限界に直面する可能性がある

#### Option B: Go（単独またはFastAPIとのマルチサービス構成）

**メリット:**

- 静的型付けによるコンパイル時のエラー検出と高い保守性
- goroutineによる高効率な並行処理、CPUバウンド処理でのパフォーマンス優位性
- シングルバイナリへのコンパイルにより、デプロイが軽量

**デメリット:**

- **LangGraphエコシステム**: LangGraph/LangChainはPython（およびTypeScript）向けに提供されている。Goでの開発はコストが大幅に増加する
- **PoCの再実装**: PoCで検証済みのWebSocket + LangGraph統合、STT/TTSパイプラインを全てGoで書き直す必要がある
- **マルチサービス構成のコスト**: 仮にFastAPI + Goの2サービス構成にした場合、サービス間通信の設計、JWT検証ロジックの二重実装、デプロイの複雑化、デバッグ時のトレーサビリティ低下といったコストが発生する。これらのコストに見合うパフォーマンス上の利益がない

#### Option C: Node.js（Express）

**メリット:**

- フロントエンド（Next.js / TypeScript）と言語を統一でき、型定義の共有やフルスタック開発の認知負荷低減が可能
- WebSocketのサポートが成熟しており、Socket.IOなどのライブラリエコシステムも豊富
- LangChain.js（TypeScript版）が利用可能

**デメリット:**

- LangGraphのTypeScript版は存在するが、Pythonのエコシステムに敵わない
- PoCのPythonコード資産が全て無駄になる
- OpenAI Whisper（STT）のサーバーサイド統合はPython SDKの方がエコシステムが充実している

#### 選定理由の要約

FastAPIモノリスを選定した決定的な理由は、**LangGraphエコシステムとの親和性**である。本アプリのコア価値は「深掘りLLMエージェントとの対話フロー」にあり、このフローの制御にLangGraphを使用することがほぼ確定している。LangGraphがPythonをファーストクラスでサポートしている以上、バックエンド言語としてPython/FastAPIを選択するのが最も合理的である。

Goの並行処理性能は魅力的だが、本アプリの処理は全てI/Oバウンド（LLM API待ち、DB I/O）であり、Goのパフォーマンス優位性が活きる場面が存在しない可能性が高い。将来的にCPUバウンドなボトルネックが実測で確認された場合にGoの導入を再検討する（YAGNI原則）。

---

## Consequences

### 良い影響

- LangGraph/LLMエコシステムとシームレスに統合でき、PoCで検証済みの学習フローをそのまま発展させられる
- モノリス構成により、サービス間通信の設計・デバッグの複雑さを回避できる。開発・デプロイ・運用がシンプルに保たれる
- Cookieベース認証により、WebSocket接続が常に認証済み状態で確立され、セキュアなリアルタイム通信が実現できる
- Better AuthのセッションCookieを直接利用することで、フロントエンドの認証フローとバックエンドの認証検証が一貫したアーキテクチャになる
