# ADR-019: 確認コードの送信を自前の Route Handler に通し、IP と宛先ごとに数える

## Status

Accepted（2026-10-27。実装は #783）

## Context

Resend の送信用ドメインを認証し、誰のアドレスにも確認コードを送れるようになった。better-auth のレート制限には次の穴があった。

- 既定の保存先はメモリで、Vercel ではインスタンスごとに別の数になる
- DB に移しても、送信の既定は IP ごとに 60 秒 3 通で、1 つの IP から 1 日 4,000 通以上送れる。IP を変えれば同じ宛先にも送り続けられる。Resend の無料枠（1 日 100 通）と送信元の評判を守れない
- `sendVerificationOTP` の例外は `runInBackgroundOrAwait` が握りつぶし、エンドポイントは成功を返す。送信に失敗しても画面には「送りました」と出る

## Decision

1. **送信の入口は `POST /api/otp`（`client/app/api/otp/route.ts`）だけ**にする。better-auth の `/email-otp/send-verification-otp` は `DISABLED_EMAIL_OTP_PATHS` で HTTP から閉じ、ハンドラの中から `auth.api.sendVerificationOTP` を呼ぶ。`disabledPaths` はルーターの `onRequest` だけにかかり、`auth.api` には効かない
2. **コードは `sendVerificationOTP` の中で送らない**。`AsyncLocalStorage`（`lib/otp-capture.ts`）でハンドラに渡し、ハンドラが `deliverOtp` で送る。送信の失敗は 502 `OTP_SEND_FAILED` で返す。ハンドラの外で発行されたコードはどこにも送らない
3. **上限**: 宛先と IP の組で 1 時間 5 通・24 時間 10 通、宛先全体で 24 時間 30 通、IP ごとに 1 時間 10 通（`lib/otp-request.ts` の `OTP_SEND_LIMITS`）。宛先だけで数えると、他人が本人の宛先に送るだけで本人を締め出せるため、組で数える。宛先全体の上限は、IP を変えながらの送りつけへの最後の歯止め。超えたら送らずに 429 `OTP_SEND_LIMIT` と `retryAfterSeconds` を返し、画面に待つ時間を出す
4. **数え方**: `email_otp_sends` に 1 送信 1 行で記録し、Postgres の関数 `reserve_email_otp_send` が宛先と IP の advisory lock の中で数えて予約する（ADR-018 と同じ考え方）。宛先は同じ受信箱に届く書き方（`+` のタグ、Gmail の `.` と `googlemail.com`）をまとめた形（`inboxKey`）で数える。送り先は入力どおりのまま。宛先と IP は `BETTER_AUTH_SECRET` の HMAC で記録し、24 時間より古い行は予約のたびに消す
5. **予約を戻すのは、コードを送れなかったときだけ**（発行できなかった・Resend が失敗した）。利用者に原因が無いため
6. IP は `x-forwarded-for` の先頭を使う（Vercel が付け直す）。取れなければ IP の上限は数えず、IP の無い送信を 1 つの組として数える。開発用の固定コードの宛先は数えない

## Reasons

- **better-auth の設定ではなく自前の入口にした理由**: 宛先ごとの上限と送信の失敗の表示は、better-auth の設定では作れない（レート制限は IP とパスの組み合わせだけで、送信の失敗は握りつぶされる）
- **表を Alembic で作り、判定を SQL の関数にした理由**: 同時のリクエストでも上限を抜けないことを、サーバーの実 DB のテストで確かめられる（`tests/integration/test_email_otp_sends.py`）。client の CI には DB が無い
- **宛先を平文で持たない理由**: 送信の記録は不正の防止のためだけに使い、誰にコードを送ったかは要らない

## Consequences

- 確認コードの入力（`/sign-in/email-otp`）の制限は better-auth のまま（コードごとに 3 回・メモリの IP 制限）。コードを得るには送信が要るので、宛先ごとの上限が総当たりの回数も頭打ちにする
- 新しい種類のコード（パスワードの再設定など）を使うときは、同じ入口を通す
- 上限の値は友人のベータでの見込み。送れないという問い合わせが来たら見直す
- IP を変え続ける相手には、宛先全体の上限（30 通）までは送られる。不特定多数に公開する前に、人間かどうかを確かめる仕組み（Turnstile など）を送信の前に足す
- `BETTER_AUTH_SECRET` を変えると、24 時間以内の記録と照合できなくなる（その間だけ数え直しになる）。`BETTER_AUTH_SECRET` はほかの理由でも変えない
