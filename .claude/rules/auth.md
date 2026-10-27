---
paths:
  - "client/lib/auth.ts"
  - "client/lib/auth-client.ts"
  - "client/lib/auth-otp.ts"
  - "client/lib/auth-hooks.ts"
  - "client/lib/dev-auth.ts"
  - "client/lib/account-deletion.ts"
  - "client/lib/otp-error.ts"
  - "client/lib/otp-*.ts"
  - "client/lib/email/**"
  - "client/app/(auth)/**"
  - "client/app/api/**"
  - "client/components/auth/**"
  - "client/better-auth_migrations/**"
  - "server/core/auth.py"
  - "server/api/dependencies.py"
---

# 認証（メール OTP・BetterAuth・JWT）

ルートの `CLAUDE.md` から分けた規約。一致するファイルを Read / Edit すると自動で読み込まれる。ログイン・OTP メール・開発用の自動ログイン・BetterAuth のスキーマを触る前に関係すると分かっているときは先に読む。

- 方式の決定は `docs/adr/013-email-otp-auth.md`。パスワード認証は無い。新規登録とログインは同じフォームを `/sign-in` と `/sign-up` の 2 つの入口から出し（文言と相互リンクだけが違い、動作は同じ。登録済みかどうかは画面で区別しない）、better-auth の `email-otp`（設定は `lib/auth-otp.ts`）と Google を使う。FastAPI の JWT 検証は認証方式に依存しない
- 確認コードの送信は `POST /api/otp`（`app/api/otp/route.ts`）だけから行う。better-auth の `/email-otp/send-verification-otp` は `DISABLED_EMAIL_OTP_PATHS` で HTTP から閉じてあり、`sendVerificationOTP` はコードを `lib/otp-capture.ts` でハンドラに渡すだけで送らない。IP と宛先ごとの上限・送信の失敗の表示もここ。方針は `docs/adr/019-otp-send-limits.md`
- メールの送信は `lib/email/send-email.ts` の `sendEmail()` だけが Resend に依存する。`RESEND_API_KEY` が無い開発環境では、コードをコンソールに出す。本番ではコードをログに出さない
- 開発環境専用の固定コードと自動ログインがある。判定は `lib/dev-auth.ts` だけが持ち（`server-only`）、詳細はそのファイルを読むこと。**効くのは `@example.test` のアドレスだけ**で、これは設定が本番に漏れても本物のユーザーのアカウントに届かないようにするための守りの本体。この制限を緩めないこと
- 本番（`NODE_ENV=production`）で開発用の変数が空でない値だと、`lib/dev-auth.ts` の読み込みが例外になる。`next build` も `NODE_ENV=production` で動くため、開発用の変数が設定されているとビルドも失敗する
- 開発用の変数に `NEXT_PUBLIC_` を付けない。ログイン画面には `lib/dev-auth.ts` で判定した真偽値だけを Server Component から渡す（`__tests__/lint/server-only-boundary.test.ts` が検査する。CI は `next build` を実行しないので `server-only` の検査は CI で効かない）
- OTP メールのロゴは `cid:` のインライン画像で付ける（HTML に外部 URL を入れない。`otp-email.test.ts` が検査する）。メールクライアントは SVG を表示しないので、PNG を `lib/email/logo-png.ts` に base64 で持つ。`app/icon.svg` を直したら、viewBox を `1.5 7.25 29.75 17.5` にして幅 240px で PNG にし直して差し替えること（`sharp` で作れる）
- 新規ユーザーの名前は、`lib/auth-hooks.ts` の `databaseHooks` がメールアドレスの `@` より前で埋める（`email-otp` は名前を空文字で作るため）
- 開発サーバーは `127.0.0.1` にだけ公開する（`docker-compose.yml`。worktree で `npm run dev -- -p 3001` を使うときも `-H 127.0.0.1` を付ける）。開発用の自動ログインが同じ LAN から届かないようにするため
- 環境変数: `RESEND_API_KEY`・`EMAIL_FROM`（開発用の変数は `lib/dev-auth.ts` を参照）
- アカウントの削除は BetterAuth の `deleteUser`。`beforeDelete`（`lib/auth.ts`）が `auth.api.signJWT` で作った `purpose: "account-deletion"` 付きの JWT（`lib/account-deletion.ts` の `deletionTokenPayload`）で FastAPI の `DELETE /api/account/data` を呼び（通常の JWT は 403）、チェックポイント・添付画像・Langfuse の trace を消してからアバターを消す。API が失敗すると例外で `user` を消さずに止まる。DB の行は `user` からの CASCADE で消えるので、`user` を参照するテーブルを足すときは `ON DELETE CASCADE` を付ける。方針は `docs/adr/016-account-deletion-and-retention.md`

## 注意事項

- **BetterAuth スキーマは静的SQLで `auth.ts` と自動同期しない**: `client/better-auth_migrations/*.sql` は生成時点のスナップショット。`client/lib/auth.ts` のプラグイン（例: `jwt()` は `jwks` テーブルを要求）を追加・変更したら `npx @better-auth/cli generate --config lib/auth.ts` で再生成してコミットすること。漏れると新環境で `relation "jwks"/"user" does not exist` になる（過去に `jwks` 欠落で認証が落ちた）
- **認証まわりの `import "server-only"` は `npx @better-auth/cli generate --config lib/auth.ts` の読み込みを失敗させる**: `lib/auth.ts` から辿れる `lib/auth-otp.ts` → `lib/dev-auth.ts` と `lib/email/send-email.ts` が持つため。スナップショットを再生成するときは、これらの import を一時的に外す（または `server-only` をスタブする）。実行後は必ず元に戻すこと
- **better-auth の更新で列が増えたら、スナップショットに加えて Alembic でも足す**: スナップショットは新しい DB にしか当たらず、本番（Railway は `preDeployCommand` で `alembic upgrade head`）とローカルの既存の DB には届かない。`to_regclass` で表の有無を確かめ、`ADD COLUMN IF NOT EXISTS` で書く（例: `jwks` の `alg`・`crv`）
- **`better-auth_migrations/` は常にスナップショット1ファイルのみに保つ**: `generate` が出すのは差分ではなくフルスキーマで、実行するたび新しいタイムスタンプ名のファイルが増える。再生成したら古いファイルを削除すること。複数残すと `make setup` のループが古い方を先に適用し、新しい方は全文 `already exists` で失敗する（`-v ON_ERROR_STOP=1` を入れる前は psql が exit 0 を返すため、古いスキーマのまま成功したように見えていた）。`migrate` サブコマンドは `client/.env.local` の `DATABASE_URL` へ直接 DDL を打つので、適用先の確認なしに使わない
- 削除はログインから `freshAge`（既定 1 日）以内のセッションでないと `SESSION_EXPIRED` で断られる。`freshAge` を変えると削除の本人確認も変わる
- Google の OAuth token は `lib/auth-hooks.ts` の account の hook で null にして保存しない。Google の API を使うときはこの hook と ADR-016 を見直す
