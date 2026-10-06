# デプロイの手順（メモ）

友達など自分以外の人にメール OTP でログインしてもらうために、アプリを公開するときの手順をまとめる。まだ実行していない。ホスティングは Railway を想定する（`server/railway.toml` がある）。

## 全体像

| 構成要素 | 中身 | 備考 |
| --- | --- | --- |
| DB | PostgreSQL 17 + pgvector | `CREATE EXTENSION vector` が使えること |
| server | FastAPI（`server/Dockerfile`） | デプロイ前に `alembic upgrade head`（`railway.toml` の `preDeployCommand`） |
| client | Next.js（`client/Dockerfile`。`output: "standalone"`） | better-auth もここで動く |
| メール | Resend | 独自ドメインの認証が必要 |
| ドメイン | 例: `example.com` | アプリの公開とメールの送信元の両方に使う |

以下、アプリを `app.example.com`、API を `api.example.com`、メールの送信元を `mail.example.com` とする。

## 1. ドメインを取得する

- レジストラ（Cloudflare など）で取得する
- アプリ・API のサブドメインはホスティング側の指示どおりに DNS へ登録する

## 2. Resend で送信用ドメインを認証する

1. Resend の **Domains** で `mail.example.com` を追加する
2. 表示される DNS レコード（SPF・DKIM）を DNS に追加し、認証が通るまで待つ
3. DMARC のレコードも追加する（迷惑メールに振り分けられにくくなる）
4. **API Keys** で本番用の鍵を作る。権限は **Sending access**、ドメインは `mail.example.com` に絞る（開発用の鍵とは分ける）

認証が通るまでは、Resend はアカウントのアドレス宛てにしか送れない。

## 3. DB を用意する

1. pgvector が使える PostgreSQL 17 を作る（Railway なら pgvector 入りのテンプレート、またはイメージ `pgvector/pgvector:pg17`）
2. **better-auth のスキーマを先に適用する**: `client/better-auth_migrations/*.sql` を本番 DB へ流す。`railway.toml` の `preDeployCommand` は alembic しか実行しないので、初回は手で行う
3. その後に server をデプロイすると、`alembic upgrade head` が実行される（外部キーで better-auth の `user` を参照するため、順番を逆にすると失敗する）

## 4. server をデプロイする

ルートディレクトリを `server/` にしてデプロイする（`railway.toml` で `Dockerfile` を使う）。

| 環境変数 | 値の例 |
| --- | --- |
| `DATABASE_URL` | 本番 DB の接続文字列 |
| `OPENAI_API_KEY` | 本番用の鍵 |
| `BETTER_AUTH_URL` | `https://app.example.com` |
| `JWKS_URL` | 省略可（`BETTER_AUTH_URL` + `/api/auth/jwks`） |
| `CORS_ORIGINS` | `https://app.example.com` |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | 使うなら |
| `LANGFUSE_TRACING_ENVIRONMENT` | `production` |
| `REVIEW_TIMEZONE` | 省略可（既定 `Asia/Tokyo`） |

## 5. client をデプロイする

ルートディレクトリを `client/` にしてデプロイする。

| 環境変数 | 値の例 |
| --- | --- |
| `DATABASE_URL` | 本番 DB の接続文字列（better-auth が使う） |
| `BETTER_AUTH_SECRET` | 本番用に新しく生成した値（開発と使い回さない） |
| `BETTER_AUTH_URL` | `https://app.example.com` |
| `NEXT_PUBLIC_BETTER_AUTH_URL` | `https://app.example.com` |
| `NEXT_PUBLIC_API_URL` | `https://api.example.com` |
| `NEXT_PUBLIC_WS_URL` | `wss://api.example.com` |
| `API_URL_INTERNAL` | 省略可（server を内部ネットワークで呼ぶときの URL） |
| `RESEND_API_KEY` | 手順 2 で作った本番用の鍵 |
| `EMAIL_FROM` | `Curigor <noreply@mail.example.com>` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google ログインを使うなら |

注意:

- **`NEXT_PUBLIC_*` はビルド時に埋め込まれる**。`client/Dockerfile` は `ARG` を宣言していないので、このままではビルドに値が渡らず、`localhost` のまま公開される。Dockerfile の builder ステージに `ARG NEXT_PUBLIC_API_URL` などを足し、ビルド時に渡す必要がある
- **開発用の変数（`DEV_FIXED_OTP`・`DEV_AUTO_LOGIN`）は本番に設定しない**。値があると `lib/dev-auth.ts` が例外を投げ、ビルドも起動も失敗する
- WebSocket は `wss://`（TLS）にする。`https://` のページから `ws://` へはつながらない

## 6. Google ログインを使う場合

Google Cloud Console の OAuth クライアントに次を登録する。

- 承認済みの JavaScript 生成元: `https://app.example.com`
- 承認済みのリダイレクト URI: `https://app.example.com/api/auth/callback/google`

公開ステータスが「テスト」のままだと、テストユーザーに登録したアカウントしかログインできない。

## 7. 公開後の確認

- [ ] 自分以外のアドレス（Gmail など）に確認コードが届き、ログインできる
- [ ] 迷惑メールフォルダに入っていない（入るなら SPF・DKIM・DMARC を見直す）
- [ ] 学習を始めて、WebSocket で応答が流れる
- [ ] ノートが生成され、ダッシュボードに復習が出る
- [ ] 開発用の自動ログイン・固定コードが効かない

## 公開前に決めておくこと

- **メール送信の失敗が画面に出ない**: better-auth は送信の失敗をログに出すだけで成功を返すため、コードが届かなくても画面には「送りました」と出る（`docs/adr/013-email-otp-auth.md`）。自分以外の人はログを見られないので、公開前に失敗を画面に出すよう直すか決める
- **画像添付の保存先**: 既定の `STORAGE_BACKEND=local` はコンテナのファイルシステムに保存するため、再デプロイで消える。S3 対応（#128）を待つか、ボリュームをマウントして `LOCAL_STORAGE_DIR` をそこへ向ける
- **アップロードの上限**: multipart はハンドラの前に全量受信されるので、リバースプロキシ側でボディの上限を設ける（#128）
- **レート制限**: better-auth のレート制限はメモリに持つ。client を複数台にするなら保存先を DB へ移す
- **費用の上限**: OpenAI・Resend（無料は月 3,000 通・1 日 100 通）の利用上限と請求アラートを設定しておく
