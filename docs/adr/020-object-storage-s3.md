# ADR-020: 添付画像とアバターを S3 互換のストレージに置き、本番は Railway の Buckets にする

## Status

Accepted（2026-10-29。実装は #791。#128 の「対話画像を S3 に」「アバターを S3 に」の 2 項目を先に済ませた）

## Context

- 本番の server は `STORAGE_BACKEND` の既定（`local`）のまま、添付画像をコンテナのディスク（`/app/storage_data`）に書いていた。Railway のコンテナはデプロイと再起動で作り直されるので、添付画像はそのたびに消えていた
- アバターは client の Route Handler が Vercel の `public/avatars/` に書いていたが、Vercel の関数は書き込めないので、本番では保存できていなかった
- Railway のボリュームは 1 台にしかつなげず、Vercel からは使えず、#128 の移行でデータを移し替えることになる

## Decision

1. **`S3ObjectStorage`** を `server/storage/` に足し、`STORAGE_BACKEND=s3` で使う。接続先は環境変数（`S3_BUCKET`・`S3_ENDPOINT_URL`・`S3_REGION`・`S3_ACCESS_KEY_ID`・`S3_SECRET_ACCESS_KEY`・`S3_ADDRESSING_STYLE`）で、Railway の Buckets・Cloudflare R2・AWS S3 のどれでもコードを変えずに使える
2. **本番の保存先は Railway の Buckets**（ユーザーの決定）。server と同じ Railway の中で完結し、保存は 1 GB あたり月 0.015 ドル、S3 の操作と Bucket からの取り出しは無料。Bucket は非公開なので、配信は server を通す
3. **アバターは FastAPI 経由**（ユーザーの決定。案 A）。`PUT /api/account/avatar` で保存し、`GET /api/avatars/{user_id}/{filename}` で配信する。保存先の鍵を持つのは server だけになり、アカウントの削除（ADR-016）も server でまとめて消せる。client の `upload-avatar` と `avatar-files` は消した
4. **アバターの配信は認証なし**。`<img src>` はヘッダーを付けられず、アバターは他人に見せる場面も無いので、ファイル名を推測できない UUID にして守る。保存のたびにファイル名が変わるので `immutable` でキャッシュさせる
5. **S3 クライアントは aiobotocore**（非同期）。操作ごとにクライアントを作る（接続の管理を持たないため。画像の頻度なら費用は小さい）
6. **テストは moto のサーバー**（`ThreadedMotoServer`）に対して行う。Issue では MinIO を予定していたが、moto のサーバーは pytest の中で立ち上がるので Docker も CI のサービスも要らず、それでいて実際の HTTP で S3 の API を話す
7. **既存の画像は移さない**。本番の画像はデプロイで消えており、切り替えた後の添付から Bucket に入る

## Consequences

- 本番は Railway の server に `STORAGE_BACKEND=s3` と Bucket の接続情報を入れて切り替える。#128 で AWS に移るときは、接続先を S3 に差し替えて、Bucket の中身をコピーする
- moto は実際の Bucket との違いを全部は再現しない。本番の Bucket での確認（アップロード・配信・削除）はマージ後に行う
- Railway の Buckets には自動のバックアップが無い。Bucket を消すと 52 時間後に戻せなくなる
- アバターの URL に `user_id` が入る。better-auth の ID は推測しにくいが、アバターの URL を知る人は、その利用者の ID も知ることになる（ID だけでは何もできない）
